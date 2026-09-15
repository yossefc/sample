import { useEffect, useRef, useState } from 'react';
import { EVENT_TYPE_ORDER, styleFor } from '../lib/constants.js';
import { normalizeExamTime } from '../lib/schedule.js';

const LOCKED_TYPES = new Set(['trip']); // same rule as the Python app

/**
 * Inline "type the event into the square" form.
 * Saves { text, type, class, start_time?, end_time? } — the stored shape the
 * existing app writes, so both apps keep reading each other's events.
 */
export default function EventEditor({ classes, defaultClass, canPickAll, existing, onSave, onCancel }) {
  const [name, setName] = useState('');
  const [type, setType] = useState('general');
  const [cls, setCls] = useState(defaultClass || classes[0] || 'all');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  // A day with a trip for this class is locked in the old app — warn, don't block.
  const conflicts = (existing || [])
    .filter((e) => LOCKED_TYPES.has(e.type) && (e.class === cls || e.class === 'all'))
    .map((e) => e.text);

  const commit = () => {
    const clean = name.trim();
    if (clean.length < 2) return setError('שם קצר מדי');
    if (clean.length > 40) return setError('שם ארוך מדי');

    const event = { text: clean, type, class: cls };
    if (type === 'bagrut') {
      const s = normalizeExamTime(start);
      const e = normalizeExamTime(end);
      if (!s || !e) return setError('יש להזין שעות תקינות');
      if (e <= s) return setError('שעת סיום חייבת להיות אחרי התחלה');
      event.text = `${clean} ${s}-${e}`;
      event.start_time = s;
      event.end_time = e;
    }
    onSave(event);
  };

  const onKey = (e) => {
    if (e.key === 'Enter') commit();
    if (e.key === 'Escape') onCancel();
  };

  const classOptions = canPickAll ? [...classes, 'all'] : classes;

  return (
    <div onClick={(e) => e.stopPropagation()} className="space-y-1 rounded-md border border-indigo-300 bg-white p-1.5 shadow-md">
      <input
        ref={inputRef}
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={onKey}
        placeholder="שם האירוע…"
        className="w-full rounded border border-slate-300 px-1.5 py-1 text-xs outline-none focus:border-indigo-500"
      />
      <div className="flex gap-1">
        <select value={type} onChange={(e) => setType(e.target.value)}
          className="min-w-0 flex-1 rounded border border-slate-300 px-1 py-1 text-[11px]">
          {EVENT_TYPE_ORDER.map((t) => <option key={t} value={t}>{styleFor(t).icon} {styleFor(t).label}</option>)}
        </select>
        <select value={cls} onChange={(e) => setCls(e.target.value)}
          className="min-w-0 flex-1 rounded border border-slate-300 px-1 py-1 text-[11px]">
          {classOptions.map((c) => <option key={c} value={c}>{c === 'all' ? 'כל הכיתות' : c}</option>)}
        </select>
      </div>
      {type === 'bagrut' && (
        <div className="flex gap-1">
          <input value={start} onChange={(e) => setStart(e.target.value)} onKeyDown={onKey}
            placeholder="התחלה 09:00" className="min-w-0 flex-1 rounded border border-slate-300 px-1.5 py-1 text-[11px]" />
          <input value={end} onChange={(e) => setEnd(e.target.value)} onKeyDown={onKey}
            placeholder="סיום 12:00" className="min-w-0 flex-1 rounded border border-slate-300 px-1.5 py-1 text-[11px]" />
        </div>
      )}
      {conflicts.length > 0 && (
        <p className="text-[10px] text-amber-700">שים לב: מתנגש עם {conflicts.join(', ')}</p>
      )}
      {error && <p className="text-[10px] text-rose-600">{error}</p>}
      <div className="flex gap-1">
        <button type="button" onClick={commit}
          className="flex-1 rounded bg-indigo-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-indigo-700">
          שמור
        </button>
        <button type="button" onClick={onCancel}
          className="rounded border border-slate-300 px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-50">
          ביטול
        </button>
      </div>
    </div>
  );
}

/** Events of a cell that belong to a class, keeping their index in the full cell. */
export function visibleEvents(cell, cls) {
  return (cell || [])
    .map((ev, index) => ({ ev, index }))
    .filter(({ ev }) => !cls || ev.class === cls || ev.class === 'all');
}

/** One event chip, with an optional delete control. */
export function EventChip({ ev, canEdit, onDelete }) {
  const s = styleFor(ev.type);
  return (
    <div title={ev.text} style={{ background: s.bg, color: s.fg, borderColor: s.border }}
      className="group flex items-center gap-1 rounded border px-1 py-0.5 text-[11px] leading-tight">
      <span className="truncate" style={{ fontWeight: s.bold ? 700 : 400 }}>{s.icon} {ev.text}</span>
      {canEdit && (
        <button type="button" onClick={(e) => { e.stopPropagation(); onDelete(); }}
          aria-label={`מחק ${ev.text}`}
          className="ms-auto hidden shrink-0 px-0.5 text-slate-500 hover:text-rose-600 group-hover:block">
          ×
        </button>
      )}
    </div>
  );
}
