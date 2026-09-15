/**
 * Builds a miniature .xlsx in memory (same shape as the Ministry's file) and
 * checks it round-trips. Run: node src/lib/ministryXlsx.test.mjs
 */
import { zipSync, strToU8 } from 'fflate';
import {
  parseMinistryXlsx, serialToDate, fractionToTime, describeSession,
} from './ministryXlsx.js';

const sharedStrings = [
  'סמל שאלון', 'שם שאלון', 'תאריך', 'משעה', 'עד שעה',
  'מחשבת ישראל דתי לע"ח', 'עברית', 'מתמטיקה & מדעים',
];

const si = sharedStrings.map((s) => `<si><t>${s.replace(/&/g, '&amp;').replace(/"/g, '&quot;')}</t></si>`).join('');

const row = (n, cells) => `<row r="${n}">${cells}</row>`;
const sCell = (ref, idx) => `<c r="${ref}" t="s"><v>${idx}</v></c>`;
const nCell = (ref, v) => `<c r="${ref}"><v>${v}</v></c>`;

const sheet = `<?xml version="1.0"?><worksheet><sheetData>
${row(1, '<c r="B1" t="inlineStr"><is><t>מעודכן ל-14.9.2026</t></is></c>')}
${row(2, sCell('A2', 0) + sCell('B2', 1) + sCell('C2', 2) + sCell('D2', 3) + sCell('E2', 4))}
${row(3, '<c r="A3"><v>38114</v></c>' + sCell('B3', 5) + nCell('C3', 46384) + nCell('D3', 0.45833333333333331) + nCell('E3', 0.51041666666666663))}
${row(4, '<c r="A4"><v>11282</v></c>' + sCell('B4', 6) + nCell('C4', 46391) + nCell('D4', 0.41666666666666669) + nCell('E4', 0.5))}
${row(5, '<c r="A5"><v>35172</v></c>' + sCell('B5', 7) + nCell('C5', 46427) + nCell('D5', 0.375) + nCell('E5', 0.4375))}
${row(6, '<c r="B6" t="inlineStr"><is><t>שורה בלי סמל</t></is></c>')}
</sheetData></worksheet>`;

const xlsx = zipSync({
  'xl/sharedStrings.xml': strToU8(`<?xml version="1.0"?><sst>${si}</sst>`),
  'xl/worksheets/sheet1.xml': strToU8(sheet),
});

const tests = {
  'converts Excel serial dates and time fractions'() {
    assertEq(serialToDate(46384), '2026-12-28');
    assertEq(serialToDate(46391), '2027-01-04');
    assertEq(fractionToTime(0.45833333333333331), '11:00');
    assertEq(fractionToTime(0.51041666666666663), '12:15');
    assertEq(fractionToTime(0.375), '09:00');
  },

  'reads the exams, skipping header and incomplete rows'() {
    const { exams } = parseMinistryXlsx(xlsx);
    assertEq(exams.length, 3);
    assertEq(exams[0].code, '38114');
    assertEq(exams[0].name, 'מחשבת ישראל דתי לע"ח');
    assertEq(exams[0].date, '2026-12-28');
    assertEq(exams[0].start_time, '11:00');
    assertEq(exams[0].end_time, '12:15');
    assertEq(exams[1].name, 'עברית');
  },

  'decodes XML entities in names'() {
    const { exams } = parseMinistryXlsx(xlsx);
    assertEq(exams[2].name, 'מתמטיקה & מדעים');
  },

  'labels a winter session that straddles the new year'() {
    // Real תשפ"ז winter data runs 28/12/2026 -> 09/02/2027.
    assertEq(describeSession(['2026-12-28', '2027-01-04', '2027-02-09']), 'מועד חורף 2027');
    assertEq(describeSession(['2027-05-25', '2027-06-14']), 'מועד קיץ 2027');
  },
};

function assertEq(a, b) { if (a !== b) throw new Error(`expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`); }

let failures = 0;
for (const [name, fn] of Object.entries(tests)) {
  try { fn(); console.log(`PASS  ${name}`); }
  catch (err) { failures += 1; console.log(`FAIL  ${name}: ${err.message}`); }
}
console.log(`\n${failures ? `${failures} FAILURE(S)` : 'ALL TESTS PASSED'}`);
process.exit(failures ? 1 : 0);
