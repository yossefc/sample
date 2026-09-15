/**
 * School-vacation rules — JavaScript port of vacation_rules.py.
 *
 * Anchored on Hebrew-calendar holidays resolved from Hebcal data, never on
 * hard-coded Gregorian dates, so the rules stay correct for תשפ"ח, תשפ"ט and on.
 *
 * Tishrei is deliberately NOT one long break: the Ministry calendar keeps the
 * week between Rosh Hashana and Yom Kippur as school days. Emitting one blanket
 * "חופשת תשרי" span was the bug this port must never reintroduce.
 *
 * All arithmetic is in UTC so results never shift with the viewer's timezone.
 */

export const HOLIDAY_RULES_VERSION = 2;

const parseDate = (s) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s ?? ''));
  return m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])) : null;
};

export const fmtDate = (d) => d.toISOString().slice(0, 10);

export const addDays = (d, n) => {
  const c = new Date(d.getTime());
  c.setUTCDate(c.getUTCDate() + n);
  return c;
};

/**
 * First day of a holiday, by title, inside the school-year window.
 * Exact title match wins over a "name ..." / "name: ..." prefix; "Erev" entries
 * are skipped. The window (Aug 1 of `year` → Aug 31 of `year+1`) makes Pesach
 * resolve to the coming spring rather than the one that just passed.
 */
export function findHoliday(holidays, name, year) {
  const nameL = name.toLowerCase();
  const seasonStart = Date.UTC(year, 7, 1);
  const seasonEnd = Date.UTC(year + 1, 7, 31);
  let exact = null;
  let prefix = null;

  for (const h of Object.values(holidays || {})) {
    const title = String(h?.title ?? '').toLowerCase();
    if (!title || title.startsWith('erev')) continue;
    const d = parseDate(h?.date);
    if (!d) continue;
    const t = d.getTime();
    if (t < seasonStart || t > seasonEnd) continue;

    if (title === nameL) {
      if (exact === null || t < exact.getTime()) exact = d;
    } else if (title.startsWith(`${nameL} `) || title.startsWith(`${nameL}:`)) {
      if (prefix === null || t < prefix.getTime()) prefix = d;
    }
  }
  return exact ?? prefix;
}

const period = (start, end, text) => ({
  start: fmtDate(start),
  end: fmtDate(end),
  text,
});

/** School vacation periods for the year starting in September `year`. */
export function calculateVacationPeriods(year, holidays) {
  const vacations = [];
  const anchor = (name) => findHoliday(holidays, name, year);

  const roshHashana = anchor('Rosh Hashana');
  const yomKippur = anchor('Yom Kippur');
  const sukkot = anchor('Sukkot');
  const sukkotEnd = anchor('Shmini Atzeret'); // = Simchat Torah in Israel

  // חופשת ראש השנה — ערב + שני ימי החג. School resumes the next day (ג' תשרי),
  // so צום גדליה is a regular school day.
  if (roshHashana) {
    vacations.push(period(addDays(roshHashana, -1), addDays(roshHashana, 1), 'חופשת ראש השנה'));
  }

  // חופשת יום כיפור — ערב + יום החג.
  if (yomKippur) {
    vacations.push(period(addDays(yomKippur, -1), yomKippur, 'חופשת יום כיפור'));
  }

  // חופשת סוכות — from the day after Yom Kippur (the Ministry's "ימי חופשה בין
  // יום הכיפורים לסוכות") through Simchat Torah inclusive.
  const sukkotStart = yomKippur ? addDays(yomKippur, 1) : (sukkot ? addDays(sukkot, -1) : null);
  if (sukkotStart && sukkotEnd) {
    vacations.push(period(sukkotStart, sukkotEnd, 'חופשת סוכות'));
  }

  // חופשת חנוכה — ~10 days from the first day.
  const chanukah = anchor('Chanukah');
  if (chanukah) vacations.push(period(chanukah, addDays(chanukah, 9), 'חופשת חנוכה'));

  // חופשת סמסטר — ~5 months in, snapped forward to Sunday.
  let semester = new Date(Date.UTC(year, 8, 1));
  semester = addDays(semester, 150);
  while (semester.getUTCDay() !== 0) semester = addDays(semester, 1);
  vacations.push(period(semester, addDays(semester, 5), 'חופשת סמסטר'));

  // חופשת פורים.
  const purim = anchor('Purim');
  if (purim) vacations.push(period(addDays(purim, -1), addDays(purim, 1), 'חופשת פורים'));

  // חופשת פסח — from the eve, ~16 days.
  const pesach = anchor('Pesach');
  if (pesach) vacations.push(period(addDays(pesach, -1), addDays(pesach, 16), 'חופשת פסח'));

  // חופשת שבועות.
  const shavuot = anchor('Shavuot');
  if (shavuot) vacations.push(period(shavuot, addDays(shavuot, 1), 'חופשת שבועות'));

  // חופשת קיץ — fixed civil dates in the second calendar year.
  vacations.push({
    start: `${year + 1}-06-21`,
    end: `${year + 1}-08-31`,
    text: 'חופשת קיץ',
  });

  return vacations;
}

/** Flatten periods into { 'YYYY-MM-DD': [labels] } — one entry per covered day. */
export function expandVacationDays(vacations) {
  const days = {};
  for (const v of vacations || []) {
    const start = parseDate(v?.start);
    const end = parseDate(v?.end);
    if (!start || !end) continue;
    for (let d = start; d.getTime() <= end.getTime(); d = addDays(d, 1)) {
      const key = fmtDate(d);
      (days[key] ||= []).push(v.text ?? '');
    }
  }
  return days;
}

/** Convert Hebcal entries to the stored { date, text, type } shape. */
export function formatHolidays(holidays) {
  return Object.values(holidays || {}).map((h) => ({
    date: h?.date ?? '',
    text: h?.hebrew ?? '',
    type: h?.category === 'holiday' ? 'holiday' : 'general',
  }));
}
