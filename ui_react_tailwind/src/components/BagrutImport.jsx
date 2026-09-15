import { useEffect, useMemo, useState } from 'react';
import { loadMinistryExams, ministryDataYear } from '../lib/schedule.js';
import { parseBagrutLines } from '../lib/bulkBagrut.js';

const SAMPLE = 'מתמטיקה | 25/04/2027 | 09:00-12:30\nאנגלית | 31/05/2027 | 09:00-12:00';

/**
 * Two ways to get bagrut exams into the schedule:
 *  - from the school's stored Ministry list (only when it matches the schedule
 *    year — we never place another session's dates), and
 *  - by pasting the dates off the Ministry's draft calendar, which is published
 *    months before the machine-readable file exists.
 */
export default function BagrutImport({ schoolId, startYear, cls, onImport, onBulkAdd, onClose }) {
  const [mode, setMode] = useState('db');
  const [exams, setExams] = useState([]);
  const [meta, setMeta] = useState({});
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [text, setText] = useState('');

  const examYear = startYear + 1;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { exams: list, meta: m } = await loadMinistryExams(schoolId);
        if (cancelled) return;
        setExams(list.sort((a, b) => String(a.name).localeCompare(String(b.name), 'he')));
        setMeta(m);
      } catch (err) {
        if (!cancelled) setError(err?.code || err?.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [schoolId]);

  const dataYear = ministryDataYear(exams);
  const official = dataYear === examYear;

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return exams;
    return exams.filter((ex) => ex.code === needle || String(ex.name ?? '').toLowerCase().includes(needle));
  }, [exams, q]);

  const parsed = useMemo(() => parseBagrutLines(text, examYear), [text, examYear]);

  const Tab = ({ id, children }) => (
    <button type="button" onClick={() => setMode(id)}
      className={`rounded-lg px-3 py-1.5 text-sm ${mode === id ? 'bg-indigo-600 text-white' : 'bg-slate-100 hover:bg-slate-200'}`}>
      {children}
    </button>
  );

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex gap-1">
          <Tab id="db">מהמאגר</Tab>
          <Tab id="paste">✍️ הדבקה מהטיוטה</Tab>
        </div>
        <button type="button" onClick={onClose} className="text-slate-500 hover:text-slate-800">✕</button>
      </div>

      {mode === 'db' ? (
        <>
          <p className="text-xs text-slate-500">
            מאגר: {meta.moed ? `${meta.moed} — ${exams.length} בחינות` : (loading ? 'טוען…' : 'ריק')}
            {cls && <> · כיתה: <b>{cls}</b></>}
          </p>

          {!loading && !error && (official ? (
            <p className="mt-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              ✅ יש תאריכים רשמיים לשנת הלוח ({examYear}).
            </p>
          ) : (
            <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
              ⚠️ משרד החינוך עדיין לא פרסם את קובץ הבחינות לשנת {examYear}. במאגר יש שנת {dataYear ?? '?'} בלבד,
              ולכן הייבוא חסום — כדי לא לשבץ תאריכים שגויים.
              <br />
              👈 יש לכם את הטיוטה? עברו ללשונית <b>הדבקה מהטיוטה</b> והזינו את התאריכים האמיתיים.
            </p>
          ))}
          {error && <p className="mt-2 text-sm text-rose-600">שגיאה: {error}</p>}

          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="חיפוש מקצוע / סמל…"
            className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />

          <ul className="mt-2 max-h-80 divide-y divide-slate-100 overflow-y-auto">
            {shown.slice(0, 200).map((ex) => (
              <li key={ex.code} className="flex items-center gap-2 py-1.5 text-sm">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{ex.name} <span className="text-slate-400">({ex.code})</span></div>
                  <div className="text-xs text-slate-500">{ex.date}{ex.start_time ? ` · ${ex.start_time}-${ex.end_time}` : ''}</div>
                </div>
                <button type="button" onClick={() => onImport(ex)} disabled={!official}
                  className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300">
                  ייבא
                </button>
              </li>
            ))}
            {!loading && shown.length === 0 && <li className="py-3 text-center text-sm text-slate-500">לא נמצאו תוצאות</li>}
          </ul>
        </>
      ) : (
        <>
          <p className="text-sm text-slate-600">
            שורה אחת לכל בחינה — <b>מקצוע | תאריך | שעות</b>. השעות אינן חובה, ושנה חסרה תושלם ל־{examYear}.
            הבחינות יתווספו לכיתה <b>{cls || '—'}</b>.
          </p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
            dir="rtl"
            placeholder={SAMPLE}
            className="mt-2 w-full rounded-lg border border-slate-300 p-2 font-mono text-sm"
          />

          {parsed.errors.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-rose-600">
              {parsed.errors.map((e) => <li key={e}>{e}</li>)}
            </ul>
          )}

          {parsed.rows.length > 0 && (
            <div className="mt-2 rounded-lg bg-slate-50 p-2">
              <p className="mb-1 text-xs font-semibold text-slate-600">{parsed.rows.length} בחינות מוכנות:</p>
              <ul className="max-h-40 space-y-0.5 overflow-y-auto text-xs text-slate-700">
                {parsed.rows.map((r) => (
                  <li key={`${r.line}-${r.name}`}>
                    🎓 {r.name} — {r.date}{r.start ? ` · ${r.start}${r.end ? `-${r.end}` : ''}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button type="button" disabled={!parsed.rows.length || !cls}
            onClick={() => { onBulkAdd(parsed.rows); setText(''); }}
            className="mt-3 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300">
            הוסף {parsed.rows.length || ''} בחינות ללוח
          </button>
        </>
      )}
    </div>
  );
}
