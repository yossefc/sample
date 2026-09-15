import { useState } from 'react';
import { DAY_KEYS, DAY_NAMES } from '../lib/constants.js';
import { addDays, fmtDate } from '../lib/vacationRules.js';
import EventEditor, { EventChip, visibleEvents } from './EventEditor.jsx';

const hebrewDayFmt = new Intl.DateTimeFormat('he-u-ca-hebrew', { day: 'numeric', month: 'long' });
const hebrewDate = (d) => { try { return hebrewDayFmt.format(d); } catch { return ''; } };
const civil = (d) => `${String(d.getUTCDate()).padStart(2, '0')}/${String(d.getUTCMonth() + 1).padStart(2, '0')}`;

/**
 * The schedule as the old app draws it: one row per week, Sunday → Shabbat,
 * the week's parasha shown in the Shabbat cell, events filtered by class.
 * Click a square to type an event into it.
 */
export default function WeekTable({ weeks, parashot, cls, canEdit, classes, canPickAll, onAdd, onDelete }) {
  const [editing, setEditing] = useState(null); // 'YYYY-MM-DD'
  const today = fmtDate(new Date());

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full table-fixed border-collapse text-right">
        <thead>
          <tr className="bg-indigo-900 text-white">
            {DAY_NAMES.map((n) => (
              <th key={n} className="border border-indigo-800 px-1 py-2 text-center text-xs font-semibold sm:text-sm">{n}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weeks.map(({ wk, wi }) => {
            const start = new Date(`${wk.start_date}T00:00:00Z`);
            const parasha = parashot?.[wk.start_date] ?? '';
            return (
              <tr key={wk.start_date} className={wi % 2 === 0 ? 'bg-white' : 'bg-slate-50/70'}>
                {DAY_KEYS.map((dk, di) => {
                  const date = addDays(start, di);
                  const dateStr = fmtDate(date);
                  const cell = wk.days?.[dk] ?? [];
                  const shown = visibleEvents(cell, cls);
                  const isToday = dateStr === today;
                  const isShabbat = dk === 'shabbat';
                  return (
                    <td
                      key={dk}
                      onClick={() => canEdit && editing !== dateStr && setEditing(dateStr)}
                      className={[
                        'h-24 w-[14.28%] border border-slate-200 p-1 align-top',
                        isShabbat ? 'bg-slate-100/70' : '',
                        isToday ? 'ring-2 ring-inset ring-indigo-400' : '',
                        canEdit ? 'cursor-text hover:bg-indigo-50/40' : '',
                      ].join(' ')}
                    >
                      <div className="flex items-baseline justify-between gap-1">
                        <span className="truncate text-[10px] leading-none text-slate-400">{hebrewDate(date)}</span>
                        <span className={`text-xs font-semibold leading-none ${isToday ? 'text-indigo-700' : 'text-slate-600'}`}>
                          {civil(date)}
                        </span>
                      </div>
                      <div className="mt-1 space-y-0.5">
                        {shown.map(({ ev, index }) => (
                          <EventChip key={`${index}-${ev.text}`} ev={ev} canEdit={canEdit}
                            onDelete={() => onDelete(dateStr, index)} />
                        ))}
                        {isShabbat && parasha && (
                          <div className="rounded border border-amber-200 bg-amber-50 px-1 py-0.5 text-[11px] font-semibold text-amber-800">
                            📖 {parasha}
                          </div>
                        )}
                        {editing === dateStr && (
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
                    </td>
                  );
                })}
              </tr>
            );
          })}
          {weeks.length === 0 && (
            <tr><td colSpan={7} className="p-6 text-center text-sm text-slate-500">אין שבועות בטווח שנבחר.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
