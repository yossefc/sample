import { useEffect, useState } from 'react';
import {
  loadPermissions, setPermission, removePermission, isValidEmail,
} from '../lib/schedule.js';

/**
 * Who may open this school, and what they may see.
 *
 * The director writes only inside their own school (schools/{id}/permissions);
 * the invited person finds the school through a collection-group query on those
 * documents. So an invitation never writes into anyone else's data.
 */
export default function StaffManager({ schoolId, classes, myEmail, onClose }) {
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(null);   // email being edited

  const [email, setEmail] = useState('');
  const [role, setRole] = useState('teacher');
  const [allowed, setAllowed] = useState([]);

  const reload = async () => {
    setLoading(true);
    try {
      setStaff((await loadPermissions(schoolId)).sort((a, b) => a.email.localeCompare(b.email)));
      setError('');
    } catch (err) {
      setError(err?.code || err?.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { reload(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [schoolId]);

  const resetForm = () => { setEditing(null); setEmail(''); setRole('teacher'); setAllowed([]); };

  const startEdit = (person) => {
    setEditing(person.email);
    setEmail(person.email);
    setRole(person.role ?? 'teacher');
    setAllowed(Array.isArray(person.allowed_classes) ? person.allowed_classes : []);
  };

  const toggleClass = (c) =>
    setAllowed((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]));

  const submit = async () => {
    const key = email.trim().toLowerCase();
    if (!isValidEmail(key)) return setError('אימייל לא תקין');
    if (key === myEmail) return setError('לא ניתן לשנות את ההרשאות של עצמכם');
    if (role === 'teacher' && allowed.length === 0) return setError('בחרו לפחות כיתה אחת למורה');

    setSaving(true);
    try {
      // A director sees every class, so their list is stored as all of them.
      await setPermission(schoolId, key, {
        role,
        allowedClasses: role === 'director' ? classes : allowed,
      });
      resetForm();
      await reload();
    } catch (err) {
      setError(`השמירה נכשלה: ${err?.code || err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const revoke = async (person) => {
    if (person.email === myEmail) return;
    if (!window.confirm(`להסיר את ${person.email} מהמוסד?`)) return;
    try {
      await removePermission(schoolId, person.email);
      await reload();
    } catch (err) {
      setError(`ההסרה נכשלה: ${err?.code || err.message}`);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-bold">👥 ניהול צוות — מי רשאי לצפות ולערוך</h2>
        <button type="button" onClick={onClose} className="text-slate-500 hover:text-slate-800">✕</button>
      </div>

      {error && <p className="mb-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}

      <ul className="divide-y divide-slate-100">
        {staff.map((person) => (
          <li key={person.email} className="flex flex-wrap items-center gap-2 py-2 text-sm">
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">
                {person.email}
                {person.email === myEmail && <span className="ms-1 text-xs text-slate-400">(את/ה)</span>}
              </div>
              <div className="text-xs text-slate-500">
                {person.role === 'director' ? '👑 מנהל — כל הכיתות' : `מורה · ${(person.allowed_classes ?? []).join(', ') || 'ללא כיתות'}`}
              </div>
            </div>
            <button type="button" onClick={() => startEdit(person)}
              className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50">עריכה</button>
            <button type="button" onClick={() => revoke(person)} disabled={person.email === myEmail}
              className="rounded-lg border border-rose-200 px-2.5 py-1 text-xs text-rose-600 hover:bg-rose-50 disabled:opacity-40">
              הסר
            </button>
          </li>
        ))}
        {!loading && staff.length === 0 && (
          <li className="py-3 text-center text-sm text-slate-500">אין עדיין אף אחד מלבדכם.</li>
        )}
        {loading && <li className="py-3 text-center text-sm text-slate-500">טוען…</li>}
      </ul>

      <div className="mt-4 rounded-xl bg-slate-50 p-3">
        <h3 className="mb-2 text-sm font-semibold">{editing ? `עריכת ${editing}` : '➕ הזמנת משתמש חדש'}</h3>

        <input value={email} onChange={(e) => setEmail(e.target.value)} disabled={Boolean(editing)}
          placeholder="כתובת Gmail של המורה" dir="ltr"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" />

        <div className="mt-2 flex gap-2">
          {[['teacher', 'מורה'], ['director', 'מנהל']].map(([value, label]) => (
            <label key={value} className="flex items-center gap-1 text-sm">
              <input type="radio" checked={role === value} onChange={() => setRole(value)} />
              {label}
            </label>
          ))}
        </div>

        {role === 'teacher' && (
          <div className="mt-2">
            <p className="mb-1 text-xs text-slate-500">כיתות שהמורה רשאי לראות ולערוך:</p>
            <div className="flex flex-wrap gap-1">
              {classes.map((c) => (
                <button key={c} type="button" onClick={() => toggleClass(c)}
                  className={`rounded-full border px-2.5 py-1 text-xs ${
                    allowed.includes(c)
                      ? 'border-indigo-600 bg-indigo-600 text-white'
                      : 'border-slate-300 bg-white hover:bg-slate-100'}`}>
                  {c}
                </button>
              ))}
              {classes.length === 0 && <span className="text-xs text-slate-400">אין כיתות במוסד</span>}
            </div>
          </div>
        )}

        <div className="mt-3 flex gap-2">
          <button type="button" onClick={submit} disabled={saving}
            className="flex-1 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:bg-slate-300">
            {saving ? 'שומר…' : (editing ? 'עדכן הרשאות' : 'הזמן')}
          </button>
          {editing && (
            <button type="button" onClick={resetForm}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-white">ביטול</button>
          )}
        </div>

        <p className="mt-2 text-xs text-slate-500">
          המוזמן נכנס לאתר עם אותה כתובת Gmail ורואה מיד את המוסד — אין צורך בסיסמה או בקוד.
        </p>
      </div>
    </div>
  );
}
