import { useEffect, useMemo, useRef, useState } from 'react';
import { loadMinistryExams, ministryCoverage, saveMinistryExams, inSchoolYear } from '../lib/schedule.js';
import { parseBagrutLines } from '../lib/bulkBagrut.js';
import { parseMinistryXlsx } from '../lib/ministryXlsx.js';
import { schoolYearLabel } from '../lib/hebrewYear.js';

const SAMPLE = 'מתמטיקה | 25/04/2027 | 09:00-12:30\nאנגלית | 31/05/2027 | 09:00-12:00';

/**
 * Three ways to get bagrut exams into the schedule:
 *  - from the school's stored Ministry list,
 *  - by uploading the Ministry's .xlsx (the browser cannot fetch it directly —
 *    that URL has no CORS headers — so the file is uploaded by hand),
 *  - by pasting dates off the draft calendar, published months before the file.
 */
export default function BagrutImport({ schoolId, startYear, cls, isDirector, onImport, onBulkAdd, onClose }) {
  const [mode, setMode] = useState('db');
  const [exams, setExams] = useState([]);
  const [meta, setMeta] = useState({});
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [text, setText] = useState('');
  const [upload, setUpload] = useState(null);   // { exams, moed } awaiting confirmation
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);

  const reload = async () => {
    setLoading(true);
    try {
      const { exams: list, meta: m } = await loadMinistryExams(schoolId);
      setExams(list.sort((a, b) => String(a.date).localeCompare(String(b.date))));
      setMeta(m);
      setError('');
    } catch (err) {
      setError(err?.code || err?.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { reload(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [schoolId]);

  const coverage = useMemo(() => ministryCoverage(exams, startYear), [exams, startYear]);
  const usable = coverage.inYear > 0;

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const base = exams.filter((ex) => inSchoolYear(ex.date, startYear));
    if (!needle) return base;
    return base.filter((ex) => ex.code === needle || String(ex.name ?? '').toLowerCase().includes(needle));
  }, [exams, q, startYear]);

  const parsed = useMemo(() => parseBagrutLines(text, startYear + 1), [text, startYear]);

  const onFile = async (file) => {
    if (!file) return;
    setError('');
    try {
      const { exams: list, moed } = parseMinistryXlsx(await file.arrayBuffer());
      if (!list.length) throw new Error('לא נמצאו בחינות בקובץ');
      setUpload({ exams: list, moed });
    } catch (err) {
      setUpload(null);
      setError(`לא ניתן לקרוא את הקובץ: ${err.message}`);
    }
  };

  const confirmUpload = async () => {
    setSaving(true);
    try {
      await saveMinistryExams(schoolId, upload.exams, upload.moed);
      setUpload(null);
      if (fileRef.current) fileRef.current.value = '';
      await reload();
      setMode('db');
    } catch (err) {
      setError(`השמירה נכשלה: ${err?.code || err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const Tab = ({ id, children }) => (
    <button type="button" onClick={() => setMode(id)}
      className={`rounded-lg px-3 py-1.5 text-sm ${mode === id ? 'bg-indigo-600 text-white' : 'bg-slate-100 hover:bg-slate-200'}`}>
      {children}
    </button>
  );

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1">
          <Tab id="db">מהמאגר</Tab>
          {isDirector && <Tab id="file">📂 העלאת קובץ משרד החינוך</Tab>}
          <Tab id="paste">✍️ הדבקה מהטיוטה</Tab>
        </div>
        <button type="button" onClick={onClose} className="text-slate-500 hover:text-slate-800">✕</button>
      </div>

      {error && <p className="mb-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      {mode === 'db' && (
        <>
          <p className="text-xs text-slate-500">
            מאגר: {meta.moed ? `${meta.moed} — ${coverage.total} בחינות` : (loading ? 'טוען…' : 'ריק')}
            {cls && <> · כיתה: <b>{cls}</b></>}
          </p>

          {!loading && (usable ? (
            <p className="mt-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              ✅ {coverage.inYear} בחינות שייכות לשנת הלוח {schoolYearLabel(startYear)}.
            </p>
          ) : (
            <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
              ⚠️ אין במאגר בחינות השייכות לשנת הלוח {schoolYearLabel(startYear)}.
              {isDirector && <> העלו את קובץ משרד החינוך בלשונית <b>📂 העלאת קובץ</b>, </>}
              או הזינו את התאריכים מהטיוטה בלשונית <b>✍️ הדבקה</b>.
            </p>
          ))}

          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="חיפוש מקצוע / סמל…"
            className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />

          <ul className="mt-2 max-h-80 divide-y divide-slate-100 overflow-y-auto">
            {shown.slice(0, 300).map((ex) => (
              <li key={ex.code} className="flex items-center gap-2 py-1.5 text-sm">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{ex.name} <span className="text-slate-400">({ex.code})</span></div>
                  <div className="text-xs text-slate-500">{ex.date}{ex.start_time ? ` · ${ex.start_time}-${ex.end_time}` : ''}</div>
                </div>
                <button type="button" onClick={() => onImport(ex)} disabled={!cls}
                  className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:bg-slate-300">
                  ייבא
                </button>
              </li>
            ))}
            {!loading && shown.length === 0 && <li className="py-3 text-center text-sm text-slate-500">אין בחינות להצגה</li>}
          </ul>
        </>
      )}

      {mode === 'file' && (
        <>
          <p className="text-sm text-slate-600">
            העלו את קובץ הבחינות של משרד החינוך (למשל <code className="text-xs">LuachWinExams2027HOURS.xlsx</code>).
            הקובץ נקרא בדפדפן ונשמר כמאגר של המוסד שלכם בלבד.
          </p>
          <input ref={fileRef} type="file" accept=".xlsx"
            onChange={(e) => onFile(e.target.files?.[0])}
            className="mt-3 w-full rounded-lg border border-slate-300 p-2 text-sm file:me-3 file:rounded file:border-0 file:bg-indigo-600 file:px-3 file:py-1.5 file:text-white" />

          {upload && (
            <div className="mt-3 rounded-lg bg-slate-50 p-3">
              <p className="text-sm font-semibold text-slate-700">
                {upload.moed} — {upload.exams.length} בחינות
                <span className="ms-2 font-normal text-slate-500">
                  ({upload.exams[0]?.date} → {upload.exams[upload.exams.length - 1]?.date})
                </span>
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {upload.exams.filter((e) => inSchoolYear(e.date, startYear)).length} מתוכן שייכות לשנת הלוח {schoolYearLabel(startYear)}.
              </p>
              <button type="button" onClick={confirmUpload} disabled={saving}
                className="mt-2 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:bg-slate-300">
                {saving ? 'שומר…' : 'שמור כמאגר המוסד'}
              </button>
            </div>
          )}
        </>
      )}

      {mode === 'paste' && (
        <>
          <p className="text-sm text-slate-600">
            שורה אחת לכל בחינה — <b>מקצוע | תאריך | שעות</b>. השעות אינן חובה, ושנה חסרה תושלם ל־{startYear + 1}.
            הבחינות יתווספו לכיתה <b>{cls || '—'}</b>.
          </p>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} dir="rtl" placeholder={SAMPLE}
            className="mt-2 w-full rounded-lg border border-slate-300 p-2 font-mono text-sm" />

          {parsed.errors.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-rose-600">{parsed.errors.map((e) => <li key={e}>{e}</li>)}</ul>
          )}
          {parsed.rows.length > 0 && (
            <div className="mt-2 rounded-lg bg-slate-50 p-2">
              <p className="mb-1 text-xs font-semibold text-slate-600">{parsed.rows.length} בחינות מוכנות:</p>
              <ul className="max-h-40 space-y-0.5 overflow-y-auto text-xs text-slate-700">
                {parsed.rows.map((r) => (
                  <li key={`${r.line}-${r.name}`}>🎓 {r.name} — {r.date}{r.start ? ` · ${r.start}${r.end ? `-${r.end}` : ''}` : ''}</li>
                ))}
              </ul>
            </div>
          )}
          <button type="button" disabled={!parsed.rows.length || !cls}
            onClick={() => { onBulkAdd(parsed.rows); setText(''); }}
            className="mt-3 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:bg-slate-300">
            הוסף {parsed.rows.length || ''} בחינות ללוח
          </button>
        </>
      )}
    </div>
  );
}
