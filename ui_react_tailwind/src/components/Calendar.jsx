import { useMemo, useState } from 'react';
import { DAY_NAMES, MONTH_NAMES_HEB } from '../lib/constants.js';
import EventEditor, { EventChip, visibleEvents } from './EventEditor.jsx';

const fmt = (d) => d.toISOString().slice(0, 10);
const utc = (y, m, d) => new Date(Date.UTC(y, m, d));

const hebrewDayFmt = new Intl.DateTimeFormat('he-u-ca-hebrew', { day: 'numeric', month: 'long' });
const hebrewDate = (d) => { try { return hebrewDayFmt.format(d); } catch { return ''; } };

/** One day square: click anywhere in it to add an event. */
function DayCell({ date, inMonth, cell, cls, canEdit, classes, canPickAll, editing, setEditing, onAdd, onDelete }) {
  const dateStr = fmt(date);
  const shown = visibleEvents(cell, cls);
  const isShabbat = date.getUTCDay() === 6;
  const isEditing = editing === dateStr;

  return (
    <div
      onClick={() => canEdit && !isEditing && setEditing(dateStr)}
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
        {shown.map(({ ev, index }) => (
          <EventChip key={`${index}-${ev.text}`} ev={ev} canEdit={canEdit} onDelete={() => onDelete(dateStr, index)} />
        ))}
        {isEditing && (
          <EventEditor
            classes={classes}
            defaultClass={cls}
            canPickAll={canPickAll}
            existing={cell}
            onSave={(ev) => { onAdd(dateStr, ev); setEditing(null); }}
            onCancel={() => setEditing(null)}
          />
        )}
      </div>
    </div>
  );
}

/** A single month as a 7-column grid starting on Sunday (RTL). */
function MonthGrid({ year, month, dayMap, compact, cellProps }) {
  const first = utc(year, month, 1);
  const startPad = first.getUTCDay();
  const daysInMonth = utc(year, month + 1, 0).getUTCDate();

  const cells = [];
  for (let i = 0; i < startPad; i += 1) cells.push({ date: utc(year, month, 1 - (startPad - i)), inMonth: false });
  for (let d = 1; d <= daysInMonth; d += 1) cells.push({ date: utc(year, month, d), inMonth: true });
  while (cells.length % 7 !== 0) {
    const last = cells[cells.length - 1].date;
    cells.push({ date: new Date(last.getTime() + 86400000), inMonth: false });
  }

  return (
    <section className="min-w-0">
      <h3 className="mb-2 text-center text-base font-bold text-indigo-900">{MONTH_NAMES_HEB[month + 1]} {year}</h3>
      <div className="grid grid-cols-7 gap-1">
        {DAY_NAMES.map((n) => <div key={n} className="pb-1 text-center text-[11px] font-semibold text-slate-500">{n}</div>)}
        {cells.map(({ date, inMonth }) => (
          <div key={fmt(date)} className={compact ? '[&>div]:min-h-[64px]' : ''}>
            <DayCell date={date} inMonth={inMonth} cell={dayMap[fmt(date)] ?? []}
              {...cellProps} canEdit={cellProps.canEdit && inMonth} />
          </div>
        ))}
      </div>
    </section>
  );
}

/** Month view, or three months laid out on one sheet. */
export default function Calendar({ anchor, view, dayMap, cls, canEdit, classes, canPickAll, onAdd, onDelete }) {
  const [editing, setEditing] = useState(null);

  const months = useMemo(() => {
    const count = view === 'quarter' ? 3 : 1;
    return Array.from({ length: count }, (_, i) => {
      const d = utc(anchor.getUTCFullYear(), anchor.getUTCMonth() + i, 1);
      return { year: d.getUTCFullYear(), month: d.getUTCMonth() };
    });
  }, [anchor, view]);

  const cellProps = { cls, canEdit, classes, canPickAll, editing, setEditing, onAdd, onDelete };

  return (
    <div className={view === 'quarter' ? 'grid gap-5 lg:grid-cols-3' : 'mx-auto max-w-4xl'}>
      {months.map(({ year, month }) => (
        <MonthGrid key={`${year}-${month}`} year={year} month={month} dayMap={dayMap}
          compact={view === 'quarter'} cellProps={cellProps} />
      ))}
    </div>
  );
}
