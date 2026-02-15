import { useState } from 'react';
import { EventEditModal } from './components/EventEditModal.jsx';

const classes = ['י\"א1', 'י\"א2', 'י\"ב1'];
const eventTypes = ['מבחן', 'בגרות', 'טיול', 'חופשה'];

const initialEvents = [
  { id: 'ev_1', name: 'מבחן מתמטיקה', type: 'מבחן' },
  { id: 'ev_2', name: 'טיול שנתי', type: 'טיול' },
];

export default function App() {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState(initialEvents);

  return (
    <main dir="rtl" className="min-h-screen p-4 sm:p-8">
      <div className="mx-auto max-w-5xl">
        <div className="rounded-2xl bg-indigo-900 text-white p-5 sm:p-7 mb-5">
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">לוח מבחנים תשפ\"ו</h1>
          <p className="text-indigo-200 text-lg mt-2">דוגמת ממשק React + Tailwind לעריכת אירוע</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-slate-700 mb-4">לחצו כדי לפתוח את חלון עריכת האירוע:</p>
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="h-11 px-5 rounded-xl bg-indigo-600 text-white font-medium hover:bg-indigo-700"
          >
            ✏️ עריכת אירוע
          </button>
        </div>
      </div>

      <EventEditModal
        open={open}
        dateLabel="חמישי · 19/02"
        classes={classes}
        eventTypes={eventTypes}
        existingEvents={events}
        onClose={() => setOpen(false)}
        onDeleteExisting={(id) => setEvents((prev) => prev.filter((ev) => ev.id !== id))}
        onSave={(data) => {
          const next = {
            id: crypto.randomUUID(),
            name: data.name,
            type: data.type,
          };
          setEvents((prev) => [next, ...prev]);
          setOpen(false);
        }}
      />
    </main>
  );
}
