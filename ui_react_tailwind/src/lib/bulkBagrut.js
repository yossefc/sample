/**
 * Parse a pasted list of bagrut exams, one per line.
 *
 * The Ministry publishes next year's dates as a draft calendar (a picture of a
 * table) long before the machine-readable Excel exists, so schools have the real
 * dates but no file to import. This lets them retype just the subjects they
 * offer instead of clicking through the calendar fifteen times.
 *
 * Accepted per line — separators may be "|", a tab, or two-plus spaces:
 *   מתמטיקה 35582 | 25/04/2027 | 09:00-12:30
 *   אנגלית | 31.5.2027
 *   תנ"ך | 2027-05-12 | 09:00
 * A date without a year falls back to `defaultYear`.
 */

const pad = (n) => String(n).padStart(2, '0');

/** "25/04/2027", "25.4.27", "2027-04-25", "25/4" -> "YYYY-MM-DD" (or null). */
export function parseDate(raw, defaultYear) {
  const s = String(raw ?? '').trim();
  if (!s) return null;

  const iso = /^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/.exec(s);
  if (iso) return `${iso[1]}-${pad(iso[2])}-${pad(iso[3])}`;

  const dmy = /^(\d{1,2})[-/.](\d{1,2})(?:[-/.](\d{2,4}))?$/.exec(s);
  if (dmy) {
    const day = Number(dmy[1]);
    const month = Number(dmy[2]);
    let year = dmy[3] ? Number(dmy[3]) : defaultYear;
    if (year != null && year < 100) year += 2000;
    if (!year || month < 1 || month > 12 || day < 1 || day > 31) return null;
    return `${year}-${pad(month)}-${pad(day)}`;
  }
  return null;
}

/** "09:00-12:30" / "9:00" -> { start, end } with zero-padded values. */
export function parseTimes(raw) {
  const s = String(raw ?? '').trim();
  if (!s) return { start: '', end: '' };
  const parts = s.split(/\s*[-–—]\s*/);
  const one = (v) => {
    const m = /^(\d{1,2}):(\d{2})$/.exec(String(v ?? '').trim());
    return m ? `${pad(m[1])}:${m[2]}` : '';
  };
  return { start: one(parts[0]), end: one(parts[1]) };
}

const splitFields = (line) => {
  if (line.includes('|')) return line.split('|');
  if (line.includes('\t')) return line.split('\t');
  return line.split(/\s{2,}/);
};

/**
 * @returns {{ rows: Array<{name,date,start,end,line:number}>, errors: string[] }}
 */
export function parseBagrutLines(text, defaultYear) {
  const rows = [];
  const errors = [];

  String(text ?? '').split('\n').forEach((rawLine, i) => {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) return;

    const fields = splitFields(line).map((f) => f.trim()).filter(Boolean);
    const name = fields[0] ?? '';
    if (!name) { errors.push(`שורה ${i + 1}: חסר שם מקצוע`); return; }

    // The date is the first field that parses as one (usually the second).
    let date = null;
    let dateIdx = -1;
    for (let f = 1; f < fields.length; f += 1) {
      const parsed = parseDate(fields[f], defaultYear);
      if (parsed) { date = parsed; dateIdx = f; break; }
    }
    if (!date) { errors.push(`שורה ${i + 1}: לא נמצא תאריך תקין ("${line}")`); return; }

    const { start, end } = parseTimes(fields[dateIdx + 1]);
    rows.push({ name, date, start, end, line: i + 1 });
  });

  return { rows, errors };
}

/** Turn a parsed row into the stored event shape (same as the Python app writes). */
export function rowToEvent(row, cls) {
  const label = row.start && row.end
    ? `בגרות ${row.name} ${row.start}-${row.end}`
    : `בגרות ${row.name}`;
  const event = { text: label, type: 'bagrut', class: cls };
  if (row.start) event.start_time = row.start;
  if (row.end) event.end_time = row.end;
  return event;
}
