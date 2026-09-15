// Shared constants. These mirror the existing Firestore documents exactly so the
// new app reads and writes the same data as the current one — no migration.

export const DAY_KEYS = [
  'sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'shabbat',
];

export const DAY_NAMES = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת'];

export const MONTH_NAMES_HEB = {
  1: 'ינואר', 2: 'פברואר', 3: 'מרץ', 4: 'אפריל', 5: 'מאי', 6: 'יוני',
  7: 'יולי', 8: 'אוגוסט', 9: 'ספטמבר', 10: 'אוקטובר', 11: 'נובמבר', 12: 'דצמבר',
};

export const EVENT_TYPE_ORDER = [
  'bagrut', 'magen', 'trip', 'vacation', 'holiday', 'general',
];

// Colours kept in sync with the current app so the two look like one product.
export const STYLES = {
  bagrut:  { bg: '#FEE2E2', fg: '#9F1239', border: '#FDA4AF', bold: true,  label: 'בגרות',        icon: '🎓' },
  magen:   { bg: '#FFEDD5', fg: '#9A3412', border: '#FDBA74', bold: true,  label: 'מגן / מתכונת', icon: '📝' },
  trip:    { bg: '#DCFCE7', fg: '#166534', border: '#86EFAC', bold: false, label: 'טיול / מסע',   icon: '🚌' },
  vacation:{ bg: '#DBEAFE', fg: '#1E40AF', border: '#93C5FD', bold: false, label: 'חופשה',        icon: '🏖️' },
  holiday: { bg: '#F3E8FF', fg: '#6B21A8', border: '#D8B4FE', bold: false, label: 'חג',           icon: '🎉' },
  general: { bg: '#F1F5F9', fg: '#334155', border: '#CBD5E1', bold: false, label: 'כללי',         icon: '📌' },
};

export const styleFor = (type) => STYLES[type] || STYLES.general;

/** Generated day markers, as opposed to events a user entered. */
export const isSystemEvent = (ev) =>
  (ev?.type === 'holiday' || ev?.type === 'vacation') && ev?.class === 'all';
