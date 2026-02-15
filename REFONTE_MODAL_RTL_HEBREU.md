# Refonte UI - Modal "עריכת אירוע" (RTL)

## 1) Diagnostic (actionnable)
1. Hiérarchie visuelle faible: titre, date, champs et actions ont un poids similaire, donc lecture lente.
2. RTL cassé dans la zone "ניהול צוות": colonnes trop étroites, texte hébreu vertical/coupé.
3. Placeholders utilisés comme labels implicites: quand le champ est rempli, le contexte disparaît.
4. Trop de largeur/hauteur non maîtrisée: la modale force le scroll et cache la confirmation d'action.
5. Actions ambiguës: suppression sans confirmation claire et bouton principal pas assez différencié.
6. Validation incomplète: règle `heure fin > heure début` non visible immédiatement.

## 2) Nouvelle maquette (claire + moderne)
- Grille: colonne unique (sauf heures sur desktop), largeur desktop `520px`, mobile plein écran.
- Spacing: `8/12/16/24` px cohérents.
- Typo: `Heebo` (fallback `Arial, sans-serif`) pour meilleure lisibilité hébreu.
- Header:
  - Titre: `עריכת אירוע`
  - Sous-info date en badge: `חמישי · 19/02`
  - Bouton fermer (X) avec `aria-label`.
- Corps (ordre RTL):
  1. `שם האירוע*`
  2. `סוג אירוע*`
  3. `כיתה יעד*`
  4. `שעת התחלה*`, `שעת סיום*` (2 colonnes seulement `sm+`)
  5. `אירועים קיימים` en chips/liste compacte avec suppression confirmée.
- Footer sticky (max 2 actions):
  - `ביטול`
  - `שמירה`

## 3) Variantes
### Variante A - Modal standard (desktop)
- Panel centré, `max-h: 90vh`, scroll interne uniquement dans le corps.
- Footer sticky visible en permanence.

### Variante B - Plein écran (mobile, recommandée)
- Panel `100dvh`, header sticky, footer sticky.
- Champs en colonne unique pour éviter erreurs de saisie.

## 4) Micro-copies (hébreu) + validations
- `שם האירוע*`  
  Aide: `שם קצר וברור (עד 40 תווים)`  
  Erreur: `יש להזין שם אירוע`
- `סוג אירוע*`  
  Aide: `בחרו סוג מהרשימה`
- `כיתה יעד*`  
  Aide: `בחרו כיתה אחת`
- `שעת התחלה*` / `שעת סיום*`  
  Erreur: `שעת הסיום חייבת להיות אחרי שעת ההתחלה`
- Suppression événement existant:
  Confirmation: `למחוק את האירוע הזה?`

Règles:
1. Tous les champs marqués `*` sont obligatoires.
2. `endTime > startTime`.
3. Longueur nom: `2..40` caractères.

## 5) Code prêt à coller (React + Tailwind + RTL)

### Fichier: `src/components/EventEditModal.tsx`
```tsx
import { Dialog, Transition } from '@headlessui/react';
import { Fragment, useMemo, useState } from 'react';

type ExistingEvent = {
  id: string;
  name: string;
  type: string;
};

type EventForm = {
  name: string;
  type: string;
  targetClass: string;
  startTime: string;
  endTime: string;
};

type Props = {
  open: boolean;
  dateLabel: string; // ex: "חמישי · 19/02"
  classes: string[];
  eventTypes: string[];
  existingEvents: ExistingEvent[];
  initial?: Partial<EventForm>;
  onClose: () => void;
  onDeleteExisting: (id: string) => void;
  onSave: (data: EventForm) => void;
};

const defaultForm: EventForm = {
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
}: Props) {
  const [form, setForm] = useState<EventForm>({ ...defaultForm, ...initial });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const canSave = useMemo(() => {
    return (
      form.name.trim().length >= 2 &&
      form.name.trim().length <= 40 &&
      !!form.type &&
      !!form.targetClass &&
      !!form.startTime &&
      !!form.endTime &&
      form.endTime > form.startTime
    );
  }, [form]);

  const setField = (key: keyof EventForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: '' }));
  };

  const validate = () => {
    const next: Record<string, string> = {};
    if (form.name.trim().length < 2) next.name = 'יש להזין שם אירוע';
    if (form.name.trim().length > 40) next.name = 'שם האירוע ארוך מדי (עד 40 תווים)';
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

  const confirmDelete = (id: string) => {
    if (window.confirm('למחוק את האירוע הזה?')) onDeleteExisting(id);
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
              <Dialog.Panel className="w-full h-[100dvh] sm:h-auto sm:max-h-[90vh] sm:max-w-[520px] bg-white shadow-2xl sm:rounded-2xl flex flex-col font-['Heebo',Arial,sans-serif]">
                <header className="sticky top-0 z-10 bg-white border-b px-4 sm:px-5 py-3 flex items-center justify-between gap-3">
                  <button
                    type="button"
                    aria-label="סגירה"
                    onClick={onClose}
                    className="h-9 w-9 rounded-lg hover:bg-slate-100 text-slate-700"
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
                    <label className="block text-sm font-medium text-slate-800 mb-1">שם האירוע*</label>
                    <input
                      value={form.name}
                      onChange={(e) => setField('name', e.target.value)}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-base focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      aria-invalid={!!errors.name}
                    />
                    <p className="text-xs text-slate-500 mt-1">שם קצר וברור (עד 40 תווים)</p>
                    {errors.name && <p className="text-xs text-rose-600 mt-1">{errors.name}</p>}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-800 mb-1">סוג אירוע*</label>
                    <select
                      value={form.type}
                      onChange={(e) => setField('type', e.target.value)}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-base bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      aria-invalid={!!errors.type}
                    >
                      <option value="">בחרו סוג אירוע</option>
                      {eventTypes.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                    {errors.type && <p className="text-xs text-rose-600 mt-1">{errors.type}</p>}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-800 mb-1">כיתה יעד*</label>
                    <select
                      value={form.targetClass}
                      onChange={(e) => setField('targetClass', e.target.value)}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-base bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      aria-invalid={!!errors.targetClass}
                    >
                      <option value="">בחרו כיתה</option>
                      {classes.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                    {errors.targetClass && <p className="text-xs text-rose-600 mt-1">{errors.targetClass}</p>}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-slate-800 mb-1">שעת התחלה*</label>
                      <input
                        type="time"
                        value={form.startTime}
                        onChange={(e) => setField('startTime', e.target.value)}
                        className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-base focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        aria-invalid={!!errors.startTime}
                      />
                      {errors.startTime && <p className="text-xs text-rose-600 mt-1">{errors.startTime}</p>}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-800 mb-1">שעת סיום*</label>
                      <input
                        type="time"
                        value={form.endTime}
                        onChange={(e) => setField('endTime', e.target.value)}
                        className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-base focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        aria-invalid={!!errors.endTime}
                      />
                      {errors.endTime && <p className="text-xs text-rose-600 mt-1">{errors.endTime}</p>}
                    </div>
                  </div>

                  <div className="pt-2">
                    <p className="text-sm font-semibold text-slate-800 mb-2">אירועים קיימים</p>
                    <div className="flex flex-wrap gap-2">
                      {existingEvents.length === 0 && (
                        <span className="text-sm text-slate-500">אין אירועים קיימים</span>
                      )}
                      {existingEvents.map((ev) => (
                        <span
                          key={ev.id}
                          className="inline-flex items-center gap-2 rounded-full bg-slate-100 text-slate-800 px-3 py-1.5 text-sm"
                        >
                          {ev.name}
                          <button
                            type="button"
                            aria-label={`מחק ${ev.name}`}
                            onClick={() => confirmDelete(ev.id)}
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
                    className="h-11 px-4 rounded-xl border border-slate-300 text-slate-800"
                  >
                    ביטול
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={!canSave}
                    className="h-11 px-5 rounded-xl bg-indigo-600 text-white disabled:opacity-50 disabled:cursor-not-allowed"
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
```

### Fichier: `src/App.tsx` (exemple d'utilisation)
```tsx
import { useState } from 'react';
import { EventEditModal } from './components/EventEditModal';

export default function App() {
  const [open, setOpen] = useState(true);

  return (
    <main dir="rtl" className="min-h-screen bg-slate-50 p-4">
      <EventEditModal
        open={open}
        dateLabel="חמישי · 19/02"
        classes={['י״א1', 'י״א2', 'י״ב1']}
        eventTypes={['מבחן', 'בגרות', 'טיול', 'חופשה']}
        existingEvents={[{ id: '1', name: 'מבחן מתמטיקה', type: 'מבחן' }]}
        onClose={() => setOpen(false)}
        onDeleteExisting={(id) => console.log('delete', id)}
        onSave={(data) => console.log('save', data)}
      />
    </main>
  );
}
```

### Dépendances
```bash
npm i @headlessui/react
```

### RTL global (recommandé)
- Dans `index.html`: `<html lang="he" dir="rtl">`
- Garder `dir="rtl"` aussi sur le conteneur racine React si besoin.
