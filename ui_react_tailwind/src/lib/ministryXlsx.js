/**
 * Read the Ministry of Education exam spreadsheet in the browser.
 *
 * The Ministry publishes files like LuachWinExams2027HOURS.xlsx with columns
 *   סמל שאלון | שם שאלון | תאריך | משעה | עד שעה
 * where the date is an Excel serial number and the hours are day fractions.
 *
 * Fetching that URL from a page is blocked by CORS, so the file is uploaded by
 * hand instead. An .xlsx is a zip of XML: fflate unzips it and the two sheets we
 * need are parsed directly — Excel's generated markup is regular enough that
 * this avoids pulling in a full spreadsheet library.
 */

import { unzipSync, strFromU8 } from 'fflate';

/** Excel serial number -> "YYYY-MM-DD" (epoch 1899-12-30, as Excel counts). */
export function serialToDate(serial) {
  const n = Number(serial);
  if (!Number.isFinite(n)) return '';
  const ms = Date.UTC(1899, 11, 30) + Math.round(n) * 86400000;
  return new Date(ms).toISOString().slice(0, 10);
}

/** Day fraction -> "HH:MM" (0.458333 -> "11:00"). */
export function fractionToTime(fraction) {
  const f = Number(fraction);
  if (!Number.isFinite(f)) return '';
  const minutes = Math.round(f * 24 * 60) % (24 * 60);
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

const decodeXmlEntities = (s) => s
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"').replace(/&apos;/g, "'")
  .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
  .replace(/&amp;/g, '&');

function parseSharedStrings(xml) {
  if (!xml) return [];
  return [...xml.matchAll(/<si>([\s\S]*?)<\/si>/g)].map((m) => {
    const text = [...m[1].matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((t) => t[1]).join('');
    return decodeXmlEntities(text);
  });
}

/** [{ rowNumber, cells: { A: value, ... } }] with shared strings resolved. */
function parseSheet(xml, shared) {
  const rows = [];
  for (const rowMatch of xml.matchAll(/<row[^>]*\br="(\d+)"[^>]*>([\s\S]*?)<\/row>/g)) {
    const cells = {};
    for (const cellMatch of rowMatch[2].matchAll(/<c\b([^>]*)>([\s\S]*?)<\/c>/g)) {
      const attrs = cellMatch[1];
      const ref = /\br="([A-Z]+)\d+"/.exec(attrs)?.[1];
      if (!ref) continue;
      const type = /\bt="([^"]+)"/.exec(attrs)?.[1];
      let value;
      if (type === 'inlineStr') {
        value = decodeXmlEntities([...cellMatch[2].matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((t) => t[1]).join(''));
      } else {
        const raw = /<v>([\s\S]*?)<\/v>/.exec(cellMatch[2])?.[1];
        if (raw == null) continue;
        value = type === 's' ? (shared[Number(raw)] ?? '') : decodeXmlEntities(raw);
      }
      cells[ref] = value;
    }
    if (Object.keys(cells).length) rows.push({ rowNumber: Number(rowMatch[1]), cells });
  }
  return rows;
}

/** Name the session the way the Python importer labels it, from the dates. */
export function describeSession(dates) {
  const valid = dates.filter(Boolean).sort();
  if (!valid.length) return '';
  const months = valid.map((d) => Number(d.slice(5, 7)));
  const winter = months.filter((m) => m === 12 || m <= 3).length;
  const summer = months.filter((m) => m >= 4 && m <= 8).length;
  const year = Number(valid[valid.length - 1].slice(0, 4));
  return `מועד ${winter >= summer ? 'חורף' : 'קיץ'} ${year}`;
}

/**
 * @param {ArrayBuffer|Uint8Array} data  the uploaded .xlsx
 * @returns {{ exams: Array<{code,name,date,start_time,end_time}>, moed: string }}
 */
export function parseMinistryXlsx(data) {
  const files = unzipSync(data instanceof Uint8Array ? data : new Uint8Array(data));
  const read = (name) => (files[name] ? strFromU8(files[name]) : '');

  const shared = parseSharedStrings(read('xl/sharedStrings.xml'));
  const sheetName = Object.keys(files).find((n) => /^xl\/worksheets\/sheet\d+\.xml$/.test(n));
  if (!sheetName) throw new Error('לא נמצא גיליון בקובץ');
  const rows = parseSheet(read(sheetName), shared);

  // Header row = the one naming the code column; data starts after it.
  const headerRow = rows.find((r) => Object.values(r.cells).some((v) => String(v).includes('סמל')));
  const firstDataRow = headerRow ? headerRow.rowNumber + 1 : 3;

  const exams = [];
  for (const { rowNumber, cells } of rows) {
    if (rowNumber < firstDataRow) continue;
    const code = String(cells.A ?? '').trim();
    const date = serialToDate(cells.C);
    if (!code || !date) continue;
    exams.push({
      code,
      name: String(cells.B ?? '').trim(),
      date,
      start_time: cells.D != null ? fractionToTime(cells.D) : '',
      end_time: cells.E != null ? fractionToTime(cells.E) : '',
    });
  }

  return { exams, moed: describeSession(exams.map((e) => e.date)) };
}
