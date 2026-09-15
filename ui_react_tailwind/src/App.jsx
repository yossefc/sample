import { useCallback, useEffect, useMemo, useState } from 'react';
import { onAuthStateChanged, signInWithPopup, signOut } from 'firebase/auth';

import Calendar from './components/Calendar.jsx';
import WeekTable from './components/WeekTable.jsx';
import BagrutImport from './components/BagrutImport.jsx';
import Legend from './components/Legend.jsx';
import { auth, googleProvider } from './lib/firebase.js';
import {
  loadUserSchools, loadWeeks, saveWeeks, saveSchoolMeta,
  weeksToDayMap, withDayEvents, findDaySlot, importExamToWeeks,
} from './lib/schedule.js';
import { regenerateYear, schoolYearStartOf } from './lib/generate.js';
import { rowToEvent } from './lib/bulkBagrut.js';
import { schoolYearLabel } from './lib/hebrewYear.js';
import { MONTH_NAMES_HEB } from './lib/constants.js';

const DAY_MS = 86400000;
const utcMonthStart = (d) => new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1));

const RANGES = [
  ['week', 'שבוע'], ['month', 'חודש'], ['sem1', 'מחצית א׳'], ['sem2', 'מחצית ב׳'], ['year', 'כל השנה'],
];

/** Weeks (with their index) overlapping the chosen range. */
function weeksInRange(weeks, range, anchor, startYear) {
  const now = new Date();
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  let lo = -Infinity;
  let hi = Infinity;
  if (range === 'week') { lo = today - now.getUTCDay() * DAY_MS; hi = lo + 6 * DAY_MS; }
  if (range === 'month') { lo = Date.UTC(anchor.getUTCFullYear(), anchor.getUTCMonth(), 1); hi = Date.UTC(anchor.getUTCFullYear(), anchor.getUTCMonth() + 1, 0); }
  if (range === 'sem1') { lo = Date.UTC(startYear, 7, 1); hi = Date.UTC(startYear + 1, 0, 31); }
  if (range === 'sem2') { lo = Date.UTC(startYear + 1, 1, 1); hi = Date.UTC(startYear + 1, 7, 31); }

  const all = weeks.map((wk, wi) => ({ wk, wi }));
  const hit = all.filter(({ wk }) => {
    const s = new Date(`${wk.start_date}T00:00:00Z`).getTime();
    return s + 6 * DAY_MS >= lo && s <= hi;
  });
  return hit.length || range !== 'week' ? hit : all.slice(0, 1);
}

export default function App() {
  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [schools, setSchools] = useState([]);
  const [school, setSchool] = useState(null);
  const [problems, setProblems] = useState([]);
  const [weeks, setWeeks] = useState([]);
  const [rev, setRev] = useState(0);
  const [parashot, setParashot] = useState({});
  const [view, setView] = useState('table');
  const [range, setRange] = useState('sem1');
  const [anchor, setAnchor] = useState(() => utcMonthStart(new Date()));
  const [cls, setCls] = useState('');
  const [showBagrut, setShowBagrut] = useState(false);
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

  // Load the selected school's schedule and pick sensible defaults.
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
        setParashot(school.parashot ?? {});
        const sy = schoolYearStartOf(w);
        setRange(Date.now() < Date.UTC(sy + 1, 1, 1) ? 'sem1' : 'sem2');
      } catch (err) {
        if (!cancelled) setStatus(`שגיאה בטעינת הלוח: ${err.message}`);
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => { cancelled = true; };
  }, [school]);

  const isDirector = school?.role === 'director';
  const canEdit = isDirector || school?.role === 'teacher';
  const classes = useMemo(() => {
    const all = school?.classes ?? [];
    const allowed = school?.allowedClasses ?? [];
    return !isDirector && allowed.length ? all.filter((c) => allowed.includes(c)) : all;
  }, [school, isDirector]);

  useEffect(() => { if (classes.length && !classes.includes(cls)) setCls(classes[0]); }, [classes, cls]);

  const startYear = useMemo(() => schoolYearStartOf(weeks), [weeks]);
  const dayMap = useMemo(() => weeksToDayMap(weeks), [weeks]);
  const tableWeeks = useMemo(() => weeksInRange(weeks, range, anchor, startYear), [weeks, range, anchor, startYear]);

  const persist = useCallback(async (nextWeeks) => {
    setWeeks(nextWeeks);                       // optimistic: the UI stays instant
    try {
      const nextRev = await saveWeeks(school.id, nextWeeks, rev);
      setRev(nextRev);
      setStatus('');
    } catch (err) {
      setStatus(err?.code === 'schedule/conflict'
        ? 'מישהו אחר עדכן את הלוח. רעננו את הדף.'
        : `השמירה נכשלה: ${err.message}`);
    }
  }, [school, rev]);

  const addEvent = useCallback((dateStr, event) => {
    if (!school || !findDaySlot(weeks, dateStr)) { setStatus('התאריך מחוץ לטווח הלוח של שנה זו'); return; }
    persist(withDayEvents(weeks, dateStr, [...(dayMap[dateStr] ?? []), event]));
  }, [school, weeks, dayMap, persist]);

  const deleteEvent = useCallback((dateStr, index) => {
    persist(withDayEvents(weeks, dateStr, (dayMap[dateStr] ?? []).filter((_, i) => i !== index)));
  }, [weeks, dayMap, persist]);

  const importExam = useCallback((exam) => {
    const { weeks: w, ok, message } = importExamToWeeks(weeks, exam, cls);
    if (!ok) { setStatus(message); return; }
    persist(w);
    setStatus(`יובא: ${exam.name}`);
  }, [weeks, cls, persist]);

  /** Add a whole pasted list of bagrut exams in one save. */
  const addBagrutRows = useCallback((rows) => {
    let next = weeks;
    let added = 0;
    const skipped = [];
    for (const row of rows) {
      const slot = findDaySlot(next, row.date);
      if (!slot) { skipped.push(`${row.name} (${row.date})`); continue; }
      const [wi, dk] = slot;
      const cell = next[wi].days?.[dk] ?? [];
      next = withDayEvents(next, row.date, [...cell, rowToEvent(row, cls)]);
      added += 1;
    }
    if (added) persist(next);
    setStatus([
      added ? `נוספו ${added} בחינות` : 'לא נוספה אף בחינה',
      skipped.length ? `מחוץ לטווח הלוח: ${skipped.join(', ')}` : '',
    ].filter(Boolean).join(' · '));
  }, [weeks, cls, persist]);

  const regenerate = useCallback(async (keepUserEvents) => {
    if (!isDirector) return;
    const warning = keepUserEvents
      ? 'לבנות מחדש את ימי המערכת (חגים, חופשות, פרשות)? האירועים שלכם יישמרו.'
      : 'אתחול מלא: כל האירועים בלוח יימחקו ויישארו רק ימי המערכת. להמשיך?';
    if (!window.confirm(warning)) return;
    setBusy(true);
    try {
      const { weeks: w, parashot: p, label, restored } = await regenerateYear(startYear, weeks, { keepUserEvents });
      const nextRev = await saveWeeks(school.id, w, rev);
      await saveSchoolMeta(school.id, { year: label, parashot: p });
      setWeeks(w); setRev(nextRev); setParashot(p);
      setStatus(`ימי המערכת נבנו מחדש ✓${restored ? ` · ${restored} אירועים שלכם נשמרו` : ''}`);
    } catch (err) {
      setStatus(`הבנייה נכשלה: ${err?.code || err.message}`);
    } finally {
      setBusy(false);
    }
  }, [isDirector, startYear, weeks, school, rev]);

  const shiftMonths = (n) => setAnchor((a) => new Date(Date.UTC(a.getUTCFullYear(), a.getUTCMonth() + n, 1)));

  if (!authReady) return <Shell><Panel>טוען…</Panel></Shell>;

  if (!user) {
    return (
      <Shell>
        <Panel>
          <h2 className="mb-4 text-xl font-bold">לוח מבחנים</h2>
          <button type="button"
            onClick={() => signInWithPopup(auth, googleProvider).catch((e) => setStatus(e.message))}
            className="h-11 w-full rounded-xl bg-indigo-600 px-5 font-medium text-white hover:bg-indigo-700">
            התחברות עם Google
          </button>
          {status && <p className="mt-3 text-sm text-rose-600">{status}</p>}
        </Panel>
      </Shell>
    );
  }

  return (
    <Shell>
      <header className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl bg-indigo-900 p-4 text-white print:mb-2 print:bg-white print:p-0 print:text-black">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-extrabold sm:text-2xl">
            לוח מבחנים {school ? schoolYearLabel(startYear) : ''}{cls ? ` · ${cls}` : ''}
          </h1>
          <p className="truncate text-sm text-indigo-200 print:text-slate-600">{school?.name ?? 'אין מוסד'}</p>
        </div>
        <div className="ms-auto flex flex-wrap items-center gap-2 print:hidden">
          {schools.length > 1 && (
            <select value={school?.id ?? ''} onChange={(e) => setSchool(schools.find((s) => s.id === e.target.value) ?? null)}
              className="rounded-lg px-2 py-1.5 text-sm text-slate-800">
              {schools.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          )}
          <button type="button" onClick={() => signOut(auth)} className="rounded-lg bg-white/10 px-3 py-1.5 text-sm hover:bg-white/20">יציאה</button>
        </div>
      </header>

      {school && (
        <div className="mb-3 space-y-2 print:hidden">
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex gap-1">
              <Btn active={view === 'table'} onClick={() => setView('table')}>📋 מערכת</Btn>
              <Btn active={view === 'month'} onClick={() => setView('month')}>חודש</Btn>
              <Btn active={view === 'quarter'} onClick={() => setView('quarter')}>3 חודשים</Btn>
            </div>

            {classes.length > 0 && (
              <select value={cls} onChange={(e) => setCls(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm">
                {classes.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            )}

            {view === 'table' ? (
              <div className="inline-flex flex-wrap gap-1">
                {RANGES.map(([key, label]) => <Btn key={key} active={range === key} onClick={() => setRange(key)}>{label}</Btn>)}
              </div>
            ) : (
              <div className="inline-flex items-center gap-1">
                <Btn onClick={() => shiftMonths(view === 'quarter' ? 3 : 1)}>›</Btn>
                <span className="min-w-[8rem] text-center text-sm font-medium text-slate-700">
                  {MONTH_NAMES_HEB[anchor.getUTCMonth() + 1]} {anchor.getUTCFullYear()}
                </span>
                <Btn onClick={() => shiftMonths(view === 'quarter' ? -3 : -1)}>‹</Btn>
                <Btn onClick={() => setAnchor(utcMonthStart(new Date()))}>היום</Btn>
              </div>
            )}

            <div className="ms-auto inline-flex flex-wrap gap-1">
              {canEdit && <Btn active={showBagrut} onClick={() => setShowBagrut((v) => !v)}>🎓 בגרויות</Btn>}
              {isDirector && (
                <Btn onClick={() => regenerate(true)} title="בונה מחדש חגים, חופשות ופרשות מהמקור, ושומר את האירועים שלכם">
                  🔄 בנה מחדש ימי מערכת
                </Btn>
              )}
              {isDirector && <Btn onClick={() => regenerate(false)} title="מוחק הכל ומשאיר רק ימי מערכת">אתחול מלא</Btn>}
              <Btn onClick={() => window.print()}>🖨️ הדפסה</Btn>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Legend />
            {busy && <span className="text-sm text-slate-500">טוען…</span>}
            {status && <span className="text-sm text-rose-600">{status}</span>}
          </div>
        </div>
      )}

      {school && showBagrut && (
        <div className="mb-4 print:hidden">
          <BagrutImport schoolId={school.id} startYear={startYear} cls={cls} isDirector={isDirector}
            onImport={importExam} onBulkAdd={addBagrutRows} onClose={() => setShowBagrut(false)} />
        </div>
      )}

      {!school ? (
        <Panel>
          <p>לא נמצא מוסד המשויך לחשבון זה.</p>
          <p className="mt-2 text-xs text-slate-500">{user.email}</p>
          {problems.length > 0 && (
            <ul className="mt-3 space-y-1 text-right text-xs text-rose-600">{problems.map((p) => <li key={p}>{p}</li>)}</ul>
          )}
        </Panel>
      ) : view === 'table' ? (
        <WeekTable weeks={tableWeeks} parashot={parashot} cls={cls} canEdit={canEdit}
          classes={classes} canPickAll={isDirector} onAdd={addEvent} onDelete={deleteEvent} />
      ) : (
        <Calendar anchor={anchor} view={view} dayMap={dayMap} cls={cls} canEdit={canEdit}
          classes={classes} canPickAll={isDirector} onAdd={addEvent} onDelete={deleteEvent} />
      )}
    </Shell>
  );
}

const Btn = ({ active, onClick, children, title }) => (
  <button type="button" onClick={onClick} title={title}
    className={`rounded-lg border px-3 py-1.5 text-sm ${active ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-300 bg-white hover:bg-slate-50'}`}>
    {children}
  </button>
);

const Shell = ({ children }) => (
  <main dir="rtl" className="min-h-screen bg-slate-100 p-3 sm:p-6 print:bg-white print:p-0">
    <div className="mx-auto max-w-[1400px]">{children}</div>
  </main>
);

const Panel = ({ children }) => (
  <div className="mx-auto mt-16 max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">{children}</div>
);
