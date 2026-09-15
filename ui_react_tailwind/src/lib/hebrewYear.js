/**
 * Gematria label for a Hebrew year, thousands omitted (5787 -> תשפ"ז).
 * Computed rather than looked up, so it stays correct for any year.
 * Port of hebrew_year_label() in db_manager.py.
 */
export function hebrewYearLabel(hebYearNum) {
  const n = hebYearNum % 1000; // the ה' (5000) is omitted by convention
  const hundreds = ['', 'ק', 'ר', 'ש', 'ת', 'תק', 'תר', 'תש', 'תת', 'תתק'];
  const tens = ['', 'י', 'כ', 'ל', 'מ', 'נ', 'ס', 'ע', 'פ', 'צ'];
  const units = ['', 'א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ז', 'ח', 'ט'];

  let letters = hundreds[Math.floor(n / 100) % 10];
  const t = Math.floor((n % 100) / 10);
  const u = n % 10;

  if (t === 1 && u === 5) {
    letters += 'טו'; // 15 -> טו (avoids spelling a name of God)
  } else if (t === 1 && u === 6) {
    letters += 'טז'; // 16 -> טז
  } else {
    letters += tens[t] + units[u];
  }

  if (letters.length >= 2) return letters.slice(0, -1) + '"' + letters.slice(-1);
  if (letters) return letters + "'";
  return String(hebYearNum);
}

/** Hebrew year number for the school year that starts in September `startYear`. */
export const hebrewYearForSchoolYear = (startYear) => startYear + 3761;

/** e.g. 2026 -> 'תשפ"ז (2026-2027)' */
export function schoolYearLabel(startYear) {
  return `${hebrewYearLabel(hebrewYearForSchoolYear(startYear))} (${startYear}-${startYear + 1})`;
}
