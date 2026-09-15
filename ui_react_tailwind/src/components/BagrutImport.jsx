import { useEffect, useMemo, useState } from 'react';
import { loadMinistryExams, ministryDataYear } from '../lib/schedule.js';

/**
 * Pick ministry (bagrut) exams from the school's stored list and drop them into
 * the schedule. Mirrors the Python popup: shows which session is loaded,
 * whether it matches the schedule year, then search + import.
 * Downloading a *new* list from the Ministry needs a server (CORS) and comes
 * with the Cloud Function slice; this covers everything already stored.
 */
export default function BagrutImport({ schoolId, startYear, cls, onImport, onClose }) {
  const [exams, setExams] = useState([]);
  const [meta, setMeta] = useState({});
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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
  const examYear = startYear + 1;
  const official = dataYear === examYear;

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return exams;
    return exams.filter((ex) => ex.code === needle || String(ex.name ?? '').toLowerCase().includes(needle));
  }, [exams, q]);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-bold">🎓 בגרויות — ייבוא ללוח</h2>
        <button type="button" onClick={onClose} className="text-slate-500 hover:text-slate-800">✕</button>
      </div>

      <p className="text-xs text-slate-500">
        מאגר: {meta.moed ? `${meta.moed} — ${exams.length} בחינות` : (loading ? 'טוען…' : 'ריק')}
        {cls && <> · כיתה: <b>{cls}</b></>}
      </p>

      {!loading && !error && (
        official ? (
          <p className="mt-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            ✅ יש תאריכים רשמיים לשנת הלוח ({examYear}).
          </p>
        ) : (
          <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
            ⚠️ אין עדיין תאריכים רשמיים לשנת הלוח ({examYear}). במאגר יש שנת {dataYear ?? '?'} בלבד —
            הייבוא יסורב, ניתן להוסיף בגרות ידנית בלחיצה על היום בלוח (סוג: בגרות).
          </p>
        )
      )}
      {error && <p className="mt-2 text-sm text-rose-600">שגיאה: {error}</p>}

      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="חיפוש מקצוע / סמל…"
        className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />

      <ul className="mt-2 max-h-80 divide-y divide-slate-100 overflow-y-auto">
        {shown.slice(0, 200).map((ex) => (
          <li key={ex.code} className="flex items-center gap-2 py-1.5 text-sm">
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">{ex.name} <span className="text-slate-400">({ex.code})</span></div>
              <div className="text-xs text-slate-500">
                {ex.date}{ex.start_time ? ` · ${ex.start_time}-${ex.end_time}` : ''}
              </div>
            </div>
            <button type="button" onClick={() => onImport(ex)} disabled={!official}
              className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300">
              ייבא
            </button>
          </li>
        ))}
        {!loading && shown.length === 0 && <li className="py-3 text-center text-sm text-slate-500">לא נמצאו תוצאות</li>}
      </ul>
    </div>
  );
}
