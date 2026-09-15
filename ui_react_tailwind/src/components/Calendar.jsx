import { useEffect, useMemo, useRef, useState } from 'react';
import { DAY_NAMES, MONTH_NAMES_HEB, EVENT_TYPE_ORDER, styleFor, isSystemEvent } from '../lib/constants.js';

const fmt = (d) => d.toISOString().slice(0, 10);
const utc = (y, m, d) => new Date(Date.UTC(y, m, d));

// The browser's own Hebrew calendar — no library needed.
const hebrewDayFmt = new Intl.DateTimeFormat('he-u-ca-hebrew', { day: 'numeric', month: 'long' });
const hebrewDate = (d) => {
  try {
    return hebrewDayFmt.format(d);
  } catch {
    return '';
  }
};

/** One day square: click anywhere in it to add an event. */
function DayCell({ date, inMonth, events, canEdit, onAdd, onDelete }) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [type, setType] = useState('general');
  const inputRef = useRef(null);

  useEffect(() => {
    if (adding) inputRef.current?.focus();
  }, [adding]);

  const commit = () => {
    const clean = name.trim();
    if (clean) onAdd(fmt(date), { text: clean, type });
    setName('');
    setAdding(false);
  };

  const isShabbat = date.getUTCDay() === 6;

  return (
    <div
      onClick={() => canEdit && !adding && setAdding(true)}
      className={[
        'min-h-[92px] rounded-lg border p-1.5 text-right transition',
        inMonth ? 'bg-white' : 'bg-slate-50/60 opacity-60',
        isShabbat ? 'border-slate-300 bg-slate-50' : 'border-slate-200',
        canEdit ? 'cursor-text hover:border-indigo-400 hover:shadow-sm' : '',
      ].join(' ')}
    >
      <div className="flex items-baseline justify-between gap-1">
        <span className="text-[10px] leading-none text-slate-400">{hebrewDate(date)}</span>
        <span className="text-sm font-semibold leading-none text-slate-700">{date.getUTCDate()}</span>
      </div>

      <div className="mt-1 space-y-0.5">
        {events.map((ev, i) => {
          const s = styleFor(ev.type);
          return (
            <div
              key={`${ev.text}-${i}`}
              title={ev.text}
              style={{ background: s.bg, color: s.fg, borderColor: s.border }}
              className="group flex items-center gap-1 rounded border px-1 py-0.5 text-[11px] leading-tight"
            >
              <span className="truncate" style={{ fontWeight: s.bold ? 700 : 400 }}>
                {s.icon} {ev.text}
              </span>
              {canEdit && (
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onDelete(fmt(date), i); }}
                  className="ms-auto hidden shrink-0 px-0.5 text-slate-500 hover:text-rose-600 group-hover:block"
                  aria-label={`מחק ${ev.text}`}
                >
                  ×
                </button>
              )}
            </div>
          );
        })}

        {adding && (
          <div onClick={(e) => e.stopPropagation()} className="space-y-1">
            <input
              ref={inputRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commit();
                if (e.key === 'Escape') { setName(''); setAdding(false); }
              }}
              onBlur={() => { if (!name.trim()) setAdding(false); }}
              placeholder="מבחן…"
              className="w-full rounded border border-indigo-300 px-1 py-0.5 text-[11px] outline-none focus:border-indigo-500"
            />
            <div className="flex gap-1">
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="min-w-0 flex-1 rounded border border-slate-300 px-1 py-0.5 text-[10px]"
              >
                {EVENT_TYPE_ORDER.map((t) => (
                  <option key={t} value={t}>{styleFor(t).label}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={commit}
                className="rounded bg-indigo-600 px-2 py-0.5 text-[10px] font-medium text-white hover:bg-indigo-700"
              >
                שמור
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** A single month, as a 7-column grid starting on Sunday (RTL). */
function MonthGrid({ year, month, dayMap, canEdit, onAdd, onDelete, compact }) {
  const first = utc(year, month, 1);
  const startPad = first.getUTCDay();                 // 0 = Sunday
  const daysInMonth = utc(year, month + 1, 0).getUTCDate();

  const cells = [];
  for (let i = 0; i < startPad; i += 1) {
    const d = utc(year, month, 1 - (startPad - i));
    cells.push({ date: d, inMonth: false });
  }
  for (let d = 1; d <= daysInMonth; d += 1) {
    cells.push({ date: utc(year, month, d), inMonth: true });
  }
  while (cells.length % 7 !== 0) {
    const last = cells[cells.length - 1].date;
    cells.push({ date: new Date(last.getTime() + 86400000), inMonth: false });
  }

  return (
    <section className="min-w-0">
      <h3 className="mb-2 text-center text-base font-bold text-indigo-900">
        {MONTH_NAMES_HEB[month + 1]} {year}
      </h3>
      <div className="grid grid-cols-7 gap-1">
        {DAY_NAMES.map((n) => (
          <div key={n} className="pb-1 text-center text-[11px] font-semibold text-slate-500">{n}</div>
        ))}
        {cells.map(({ date, inMonth }) => (
          <div key={fmt(date)} className={compact ? '[&>div]:min-h-[64px]' : ''}>
            <DayCell
              date={date}
              inMonth={inMonth}
              events={dayMap[fmt(date)] ?? []}
              canEdit={canEdit && inMonth}
              onAdd={onAdd}
              onDelete={onDelete}
            />
          </div>
        ))}
      </div>
    </section>
  );
}

/** Month view, or three months laid out on one sheet. */
export default function Calendar({ anchor, view, dayMap, canEdit, onAdd, onDelete }) {
  const months = useMemo(() => {
    const count = view === 'quarter' ? 3 : 1;
    return Array.from({ length: count }, (_, i) => {
      const d = utc(anchor.getUTCFullYear(), anchor.getUTCMonth() + i, 1);
      return { year: d.getUTCFullYear(), month: d.getUTCMonth() };
    });
  }, [anchor, view]);

  return (
    <div className={view === 'quarter'
      ? 'grid gap-5 lg:grid-cols-3'
      : 'mx-auto max-w-4xl'}
    >
      {months.map(({ year, month }) => (
        <MonthGrid
          key={`${year}-${month}`}
          year={year}
          month={month}
          dayMap={dayMap}
          canEdit={canEdit}
          onAdd={onAdd}
          onDelete={onDelete}
          compact={view === 'quarter'}
        />
      ))}
    </div>
  );
}

export { isSystemEvent };
