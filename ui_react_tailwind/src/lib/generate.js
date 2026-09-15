/**
 * School-year generation — port of generate_new_year() plus the user-event
 * preservation added to the Python app.
 *
 * System days (חגים, חופשות, פרשות) are always rebuilt from scratch from Hebcal
 * with the tested vacation rules; events people typed in are carried over by
 * date. Nothing here reads the stored global_holidays document, so the stale
 * blanket "חופשת תשרי" record can never leak back in.
 */

import { fetchHebrewHolidays, fetchParashot } from './hebcal.js';
import { hebrewYearLabel, hebrewYearForSchoolYear } from './hebrewYear.js';
import { isSystemEvent, DAY_KEYS } from './constants.js';
import {
  calculateVacationPeriods, expandVacationDays, formatHolidays, addDays, fmtDate,
} from './vacationRules.js';
import { buildYearWeeks, applySystemDays, findDaySlot } from './schedule.js';

/** { 'YYYY-MM-DD': userEvents[] } — everything that isn't a generated marker. */
export function collectUserEvents(weeks) {
  const saved = {};
  for (const wk of weeks || []) {
    const start = wk?.start_date ? new Date(`${wk.start_date}T00:00:00Z`) : null;
    if (!start || Number.isNaN(start.getTime())) continue;
    DAY_KEYS.forEach((dk, i) => {
      const user = (wk?.days?.[dk] ?? []).filter((ev) => !isSystemEvent(ev));
      if (user.length) saved[fmtDate(addDays(start, i))] = user;
    });
  }
  return saved;
}

/** Re-attach preserved user events onto freshly generated weeks, by date. */
export function restoreUserEvents(weeks, saved) {
  let out = weeks;
  let restored = 0;
  for (const [dateStr, events] of Object.entries(saved || {})) {
    const slot = findDaySlot(out, dateStr);
    if (!slot) continue;
    const [wi, dk] = slot;
    out = out.map((wk, i) => (
      i === wi ? { ...wk, days: { ...wk.days, [dk]: [...(wk.days[dk] ?? []), ...events] } } : wk
    ));
    restored += events.length;
  }
  return { weeks: out, restored };
}

/** Fetch everything a school year needs from Hebcal and derive the vacations. */
export async function buildSystemDays(startYear) {
  const [h1, h2, parashot] = await Promise.all([
    fetchHebrewHolidays(startYear),
    fetchHebrewHolidays(startYear + 1),
    fetchParashot(startYear, startYear + 1),
  ]);
  const merged = { ...h1, ...h2 };
  return {
    holidays: formatHolidays(merged),
    vacationDays: expandVacationDays(calculateVacationPeriods(startYear, merged)),
    parashot,
    label: hebrewYearLabel(hebrewYearForSchoolYear(startYear)),
  };
}

/**
 * Build (or rebuild) a school year.
 * @param {number} startYear   September of the school year
 * @param {Array}  existing    current weeks, whose user events are preserved
 * @param {object} opts        { keepUserEvents = true }
 */
export async function regenerateYear(startYear, existing = [], { keepUserEvents = true } = {}) {
  const preserved = keepUserEvents ? collectUserEvents(existing) : {};
  const { holidays, vacationDays, parashot, label } = await buildSystemDays(startYear);

  let weeks = applySystemDays(buildYearWeeks(startYear), holidays, vacationDays);
  const { weeks: withUser, restored } = restoreUserEvents(weeks, preserved);
  weeks = withUser;

  return { weeks, parashot, label, restored };
}

/** September of the school year the given weeks belong to. */
export function schoolYearStartOf(weeks) {
  const first = weeks?.[0]?.start_date;
  if (!first) return new Date().getUTCFullYear();
  const d = new Date(`${first}T00:00:00Z`);
  return d.getUTCMonth() >= 7 ? d.getUTCFullYear() : d.getUTCFullYear() - 1;
}
