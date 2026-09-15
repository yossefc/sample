/**
 * Hebcal API access from the browser (the API is CORS-enabled).
 * Ports fetch_hebrew_holidays() and fetch_parasha_from_api() from the Python app.
 * Israeli calendar (geonameid 281184 = Jerusalem, i=off).
 */

import { addDays, fmtDate } from './vacationRules.js';

const HEBCAL = 'https://www.hebcal.com/hebcal';

async function fetchItems(params) {
  const url = `${HEBCAL}?${new URLSearchParams({
    v: '1', cfg: 'json', month: 'x', geo: 'geoname', geonameid: '281184', ...params,
  })}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Hebcal ${res.status}`);
  return (await res.json()).items ?? [];
}

/** Holidays for one civil year, keyed "title|date" like the Python side. */
export async function fetchHebrewHolidays(year) {
  const holidays = {};
  for (const item of await fetchItems({ year: String(year), i: 'off' })) {
    if (item.category !== 'holiday' && item.category !== 'roshchodesh') continue;
    const date = item.date;
    if (!date) continue;
    const title = item.title ?? '';
    holidays[`${title}|${date}`] = {
      date,
      hebrew: item.hebrew ?? title,
      category: item.category,
      title,
    };
  }
  return holidays;
}

/** { sundayDate: hebrewParashaName } for the school year — keyed by the week's Sunday. */
export async function fetchParashot(startYear, endYear) {
  const map = {};
  for (let year = startYear; year <= endYear; year += 1) {
    try {
      for (const item of await fetchItems({ year: String(year), s: 'on' })) {
        if (item.category !== 'parashat' || !item.date) continue;
        const shabbat = new Date(`${item.date}T00:00:00Z`);
        if (Number.isNaN(shabbat.getTime())) continue;
        map[fmtDate(addDays(shabbat, -6))] = item.hebrew ?? item.title ?? '';
      }
    } catch {
      /* one bad year must not lose the other */
    }
  }
  return map;
}
