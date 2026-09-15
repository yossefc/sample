import { EVENT_TYPE_ORDER, styleFor } from '../lib/constants.js';

export default function Legend() {
  return (
    <div className="flex flex-wrap gap-1.5 text-[11px]">
      {EVENT_TYPE_ORDER.map((t) => {
        const s = styleFor(t);
        return (
          <span key={t} style={{ background: s.bg, color: s.fg, borderColor: s.border, fontWeight: s.bold ? 700 : 400 }}
            className="rounded-full border px-2 py-0.5">
            {s.icon} {s.label}
          </span>
        );
      })}
      <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 font-semibold text-amber-800">📖 פרשת השבוע</span>
    </div>
  );
}
