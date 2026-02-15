import { Dialog, Transition } from '@headlessui/react';
import { Fragment, useMemo, useState } from 'react';

const defaultForm = {
  name: '',
  type: '',
  targetClass: '',
  startTime: '',
  endTime: '',
};

export function EventEditModal({
  open,
  dateLabel,
  classes,
  eventTypes,
  existingEvents,
  initial,
  onClose,
  onDeleteExisting,
  onSave,
}) {
  const [form, setForm] = useState({ ...defaultForm, ...(initial || {}) });
  const [errors, setErrors] = useState({});

  const canSave = useMemo(() => {
    return (
      form.name.trim().length >= 2 &&
      form.name.trim().length <= 40 &&
      form.type &&
      form.targetClass &&
      form.startTime &&
      form.endTime &&
      form.endTime > form.startTime
    );
  }, [form]);

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: '' }));
  };

  const validate = () => {
    const next = {};

    if (form.name.trim().length < 2) {
      next.name = 'יש להזין שם אירוע';
    } else if (form.name.trim().length > 40) {
      next.name = 'שם האירוע ארוך מדי (עד 40 תווים)';
    }

    if (!form.type) next.type = 'יש לבחור סוג אירוע';
    if (!form.targetClass) next.targetClass = 'יש לבחור כיתה';
    if (!form.startTime) next.startTime = 'יש להזין שעת התחלה';
    if (!form.endTime) next.endTime = 'יש להזין שעת סיום';

    if (form.startTime && form.endTime && form.endTime <= form.startTime) {
      next.endTime = 'שעת הסיום חייבת להיות אחרי שעת ההתחלה';
    }

    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSave = () => {
    if (!validate()) return;
    onSave({ ...form, name: form.name.trim() });
  };

  const confirmDelete = (id) => {
    if (window.confirm('למחוק את האירוע הזה?')) {
      onDeleteExisting(id);
    }
  };

  return (
    <Transition.Root show={open} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-slate-900/40" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto" dir="rtl">
          <div className="flex min-h-full items-stretch sm:items-center justify-center p-0 sm:p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-200"
              enterFrom="opacity-0 translate-y-2 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-150"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-2 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="w-full h-[100dvh] sm:h-auto sm:max-h-[90vh] sm:max-w-[520px] bg-white shadow-2xl sm:rounded-2xl flex flex-col">
                <header className="sticky top-0 z-10 bg-white border-b px-4 sm:px-5 py-3 flex items-center justify-between gap-3">
                  <button
                    type="button"
                    aria-label="סגירה"
                    onClick={onClose}
                    className="h-9 w-9 rounded-lg text-slate-700 hover:bg-slate-100"
                  >
                    ✕
                  </button>

                  <div className="text-right min-w-0">
                    <Dialog.Title className="text-xl font-bold text-slate-900">עריכת אירוע</Dialog.Title>
                    <p className="text-sm text-slate-600">{dateLabel}</p>
                  </div>
                </header>

                <section className="flex-1 overflow-y-auto px-4 sm:px-5 py-4 space-y-4">
                  <div>
                    <label className="label">שם האירוע*</label>
                    <input
                      value={form.name}
                      onChange={(e) => setField('name', e.target.value)}
                      className="input-field"
                      aria-invalid={Boolean(errors.name)}
                    />
                    <p className="help">שם קצר וברור (עד 40 תווים)</p>
                    {errors.name ? <p className="error">{errors.name}</p> : null}
                  </div>

                  <div>
                    <label className="label">סוג אירוע*</label>
                    <select
                      value={form.type}
                      onChange={(e) => setField('type', e.target.value)}
                      className="input-field"
                      aria-invalid={Boolean(errors.type)}
                    >
                      <option value="">בחרו סוג אירוע</option>
                      {eventTypes.map((eventType) => (
                        <option key={eventType} value={eventType}>
                          {eventType}
                        </option>
                      ))}
                    </select>
                    {errors.type ? <p className="error">{errors.type}</p> : null}
                  </div>

                  <div>
                    <label className="label">כיתה יעד*</label>
                    <select
                      value={form.targetClass}
                      onChange={(e) => setField('targetClass', e.target.value)}
                      className="input-field"
                      aria-invalid={Boolean(errors.targetClass)}
                    >
                      <option value="">בחרו כיתה</option>
                      {classes.map((schoolClass) => (
                        <option key={schoolClass} value={schoolClass}>
                          {schoolClass}
                        </option>
                      ))}
                    </select>
                    {errors.targetClass ? <p className="error">{errors.targetClass}</p> : null}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="label">שעת התחלה*</label>
                      <input
                        type="time"
                        value={form.startTime}
                        onChange={(e) => setField('startTime', e.target.value)}
                        className="input-field"
                        aria-invalid={Boolean(errors.startTime)}
                      />
                      {errors.startTime ? <p className="error">{errors.startTime}</p> : null}
                    </div>

                    <div>
                      <label className="label">שעת סיום*</label>
                      <input
                        type="time"
                        value={form.endTime}
                        onChange={(e) => setField('endTime', e.target.value)}
                        className="input-field"
                        aria-invalid={Boolean(errors.endTime)}
                      />
                      {errors.endTime ? <p className="error">{errors.endTime}</p> : null}
                    </div>
                  </div>

                  <div className="pt-1">
                    <p className="text-sm font-semibold text-slate-800 mb-2">אירועים קיימים</p>
                    <div className="flex flex-wrap gap-2">
                      {existingEvents.length === 0 ? (
                        <span className="text-sm text-slate-500">אין אירועים קיימים</span>
                      ) : null}

                      {existingEvents.map((eventItem) => (
                        <span
                          key={eventItem.id}
                          className="inline-flex items-center gap-2 rounded-full bg-slate-100 text-slate-800 px-3 py-1.5 text-sm"
                        >
                          {eventItem.name}
                          <button
                            type="button"
                            aria-label={`מחק ${eventItem.name}`}
                            onClick={() => confirmDelete(eventItem.id)}
                            className="text-rose-600 hover:text-rose-700"
                          >
                            🗑
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                </section>

                <footer className="sticky bottom-0 bg-white border-t px-4 sm:px-5 py-3 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={onClose}
                    className="h-11 px-4 rounded-xl border border-slate-300 text-slate-800 hover:bg-slate-50"
                  >
                    ביטול
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={!canSave}
                    className="h-11 px-5 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    שמירה
                  </button>
                </footer>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
}
