import { useCallback, useEffect, useMemo, useState } from 'react';
import { onAuthStateChanged, signInWithPopup, signOut } from 'firebase/auth';

import Calendar from './components/Calendar.jsx';
import { auth, googleProvider, isFirebaseConfigured } from './lib/firebase.js';
import { loadUserSchools, loadWeeks, saveWeeks, weeksToDayMap, withDayEvents, findDaySlot } from './lib/schedule.js';
import { schoolYearLabel } from './lib/hebrewYear.js';
import { MONTH_NAMES_HEB } from './lib/constants.js';

const utcMonthStart = (d) => new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1));

export default function App() {
  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [schools, setSchools] = useState([]);
  const [school, setSchool] = useState(null);
  const [problems, setProblems] = useState([]);
  const [weeks, setWeeks] = useState([]);
  const [rev, setRev] = useState(0);
  const [view, setView] = useState('month');
  const [anchor, setAnchor] = useState(() => utcMonthStart(new Date()));
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => onAuthStateChanged(auth, (u) => { setUser(u); setAuthReady(true); }), []);

  // Which schools may this user open?
  useEffect(() => {
    if (!user?.email) { setSchools([]); setSchool(null); return; }
    let cancelled = false;
    (async () => {
      try {
        const { schools: list, problems: found } = await loadUserSchools(user.email);
        if (cancelled) return;
        setSchools(list);
        setProblems(found);
        setSchool((cur) => cur ?? list[0] ?? null);
      } catch (err) {
        if (!cancelled) setStatus(`שגיאה בטעינת המוסדות: ${err.message}`);
      }
    })();
    return () => { cancelled = true; };
  }, [user]);

  // Load the selected school's schedule.
  useEffect(() => {
    if (!school?.id) { setWeeks([]); return; }
    let cancelled = false;
    (async () => {
      setBusy(true);
      try {
        const { weeks: w, rev: r } = await loadWeeks(school.id);
        if (cancelled) return;
        setWeeks(w);
        setRev(r);
      } catch (err) {
        if (!cancelled) setStatus(`שגיאה בטעינת הלוח: ${err.message}`);
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => { cancelled = true; };
  }, [school]);

  const dayMap = useMemo(() => weeksToDayMap(weeks), [weeks]);
  const canEdit = Boolean(school) && (school.role === 'director' || school.role === 'teacher');

  const persist = useCallback(async (nextWeeks) => {
    setWeeks(nextWeeks);                       // optimistic: the UI stays instant
    try {
      const nextRev = await saveWeeks(school.id, nextWeeks, rev);
      setRev(nextRev);
      setStatus('');
    } catch (err) {
      if (err?.code === 'schedule/conflict') {
        setStatus('מישהו אחר עדכן את הלוח. רעננו את הדף.');
      } else {
        setStatus(`השמירה נכשלה: ${err.message}`);
      }
    }
  }, [school, rev]);

  const addEvent = useCallback((dateStr, event) => {
    if (!school || !findDaySlot(weeks, dateStr)) {
      setStatus('התאריך מחוץ לטווח הלוח של שנה זו');
      return;
    }
    const current = dayMap[dateStr] ?? [];
    persist(withDayEvents(weeks, dateStr, [...current, { ...event, class: 'all' }]));
  }, [school, weeks, dayMap, persist]);

  const deleteEvent = useCallback((dateStr, index) => {
    const current = dayMap[dateStr] ?? [];
    persist(withDayEvents(weeks, dateStr, current.filter((_, i) => i !== index)));
  }, [weeks, dayMap, persist]);

  const shiftMonths = (n) => setAnchor((a) => new Date(Date.UTC(a.getUTCFullYear(), a.getUTCMonth() + n, 1)));

  if (!isFirebaseConfigured()) {
    return (
      <Shell>
        <Panel>
          <h2 className="mb-2 text-lg font-bold">חסרה הגדרת Firebase</h2>
          <p className="text-sm text-slate-600">
            יש להגדיר את משתני הסביבה <code>VITE_FIREBASE_API_KEY</code> ו-<code>VITE_FIREBASE_APP_ID</code>.
          </p>
        </Panel>
      </Shell>
    );
  }

  if (!authReady) return <Shell><Panel>טוען…</Panel></Shell>;

  if (!user) {
    return (
      <Shell>
        <Panel>
          <h2 className="mb-4 text-xl font-bold">לוח מבחנים</h2>
          <button
            type="button"
            onClick={() => signInWithPopup(auth, googleProvider).catch((e) => setStatus(e.message))}
            className="h-11 w-full rounded-xl bg-indigo-600 px-5 font-medium text-white hover:bg-indigo-700"
          >
            התחברות עם Google
          </button>
          {status && <p className="mt-3 text-sm text-rose-600">{status}</p>}
        </Panel>
      </Shell>
    );
  }

  return (
    <Shell>
      <header className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl bg-indigo-900 p-4 text-white">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-extrabold sm:text-2xl">
            לוח מבחנים {school ? schoolYearLabel(schoolYearStart(weeks)) : ''}
          </h1>
          <p className="truncate text-sm text-indigo-200">{school?.name ?? 'אין מוסד'}</p>
        </div>

        <div className="ms-auto flex flex-wrap items-center gap-2">
          {schools.length > 1 && (
            <select
              value={school?.id ?? ''}
              onChange={(e) => setSchool(schools.find((s) => s.id === e.target.value) ?? null)}
              className="rounded-lg px-2 py-1.5 text-sm text-slate-800"
            >
              {schools.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          )}
          <button type="button" onClick={() => signOut(auth)}
            className="rounded-lg bg-white/10 px-3 py-1.5 text-sm hover:bg-white/20">
            יציאה
          </button>
        </div>
      </header>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="inline-flex overflow-hidden rounded-lg border border-slate-300">
          <button type="button" onClick={() => setView('month')}
            className={`px-3 py-1.5 text-sm ${view === 'month' ? 'bg-indigo-600 text-white' : 'bg-white'}`}>
            חודש
          </button>
          <button type="button" onClick={() => setView('quarter')}
            className={`px-3 py-1.5 text-sm ${view === 'quarter' ? 'bg-indigo-600 text-white' : 'bg-white'}`}>
            3 חודשים
          </button>
        </div>

        <div className="inline-flex items-center gap-1">
          <button type="button" onClick={() => shiftMonths(view === 'quarter' ? 3 : 1)}
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm">›</button>
          <span className="min-w-[8rem] text-center text-sm font-medium text-slate-700">
            {MONTH_NAMES_HEB[anchor.getUTCMonth() + 1]} {anchor.getUTCFullYear()}
          </span>
          <button type="button" onClick={() => shiftMonths(view === 'quarter' ? -3 : -1)}
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm">‹</button>
        </div>

        <button type="button" onClick={() => setAnchor(utcMonthStart(new Date()))}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm">היום</button>

        <button type="button" onClick={() => window.print()}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm">🖨️ הדפסה</button>

        {busy && <span className="text-sm text-slate-500">טוען…</span>}
        {status && <span className="text-sm text-rose-600">{status}</span>}
      </div>

      {school ? (
        <Calendar
          anchor={anchor}
          view={view}
          dayMap={dayMap}
          canEdit={canEdit}
          onAdd={addEvent}
          onDelete={deleteEvent}
        />
      ) : (
        <Panel>
          <p>לא נמצא מוסד המשויך לחשבון זה.</p>
          <p className="mt-2 text-xs text-slate-500">{user.email}</p>
          {problems.length > 0 && (
            <ul className="mt-3 space-y-1 text-right text-xs text-rose-600">
              {problems.map((p) => <li key={p}>{p}</li>)}
            </ul>
          )}
        </Panel>
      )}
    </Shell>
  );
}

/** September of the school year the loaded weeks belong to. */
function schoolYearStart(weeks) {
  const first = weeks?.[0]?.start_date;
  if (!first) return new Date().getUTCFullYear();
  const d = new Date(`${first}T00:00:00Z`);
  return d.getUTCMonth() >= 7 ? d.getUTCFullYear() : d.getUTCFullYear() - 1;
}

const Shell = ({ children }) => (
  <main dir="rtl" className="min-h-screen bg-slate-100 p-3 sm:p-6">
    <div className="mx-auto max-w-[1400px]">{children}</div>
  </main>
);

const Panel = ({ children }) => (
  <div className="mx-auto mt-16 max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
    {children}
  </div>
);
