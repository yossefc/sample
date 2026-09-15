/**
 * Mirrors tests/test_vacations.py so the JS port is provably equivalent to the
 * Python rules. Run:  node src/lib/vacationRules.test.mjs
 */

import { calculateVacationPeriods, expandVacationDays } from './vacationRules.js';

const hebcal = (entries) =>
  Object.fromEntries(entries.map(([title, date]) => [
    `${title}|${date}`,
    { date, hebrew: title, category: 'holiday', title },
  ]));

// Real, verified Tishrei תשפ"ז dates (school year starting Sept 2026).
const TISHREI_5787 = hebcal([
  ['Erev Rosh Hashana', '2026-09-11'],
  ['Rosh Hashana 5787', '2026-09-12'],
  ['Rosh Hashana II', '2026-09-13'],
  ['Tzom Gedaliah', '2026-09-14'],
  ['Erev Yom Kippur', '2026-09-20'],
  ['Yom Kippur', '2026-09-21'],
  ['Erev Sukkot', '2026-09-25'],
  ['Sukkot I', '2026-09-26'],
  ['Shmini Atzeret', '2026-10-03'],
]);

const daysFor = (year, holidays) =>
  expandVacationDays(calculateVacationPeriods(year, holidays));

function span(first, last) {
  const out = [];
  const end = new Date(`${last}T00:00:00Z`).getTime();
  for (let d = new Date(`${first}T00:00:00Z`); d.getTime() <= end; d.setUTCDate(d.getUTCDate() + 1)) {
    out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

const tests = {
  'school week between Rosh Hashana and Yom Kippur is not vacation'() {
    const days = daysFor(2026, TISHREI_5787);
    for (const date of span('2026-09-14', '2026-09-18')) {
      assert(!(date in days), `${date} should be a school day, got ${days[date]}`);
    }
  },

  'festival days are vacation'() {
    const days = daysFor(2026, TISHREI_5787);
    for (const date of [...span('2026-09-12', '2026-09-13'),
                        ...span('2026-09-20', '2026-09-21'),
                        ...span('2026-09-26', '2026-10-03')]) {
      assert(date in days, `${date} should be vacation`);
    }
  },

  'Shabbat 19/09 carries no vacation tag'() {
    assert(!('2026-09-19' in daysFor(2026, TISHREI_5787)));
  },

  'blanket Tishrei label is never produced'() {
    const labels = new Set(calculateVacationPeriods(2026, TISHREI_5787).map((v) => v.text));
    assert(!labels.has('חופשת תשרי'), 'the blanket label came back');
    for (const l of ['חופשת ראש השנה', 'חופשת יום כיפור', 'חופשת סוכות']) {
      assert(labels.has(l), `missing ${l}`);
    }
  },

  'rules are generic, not hardcoded to 2026'() {
    const shifted = hebcal([
      ['Rosh Hashana 5788', '2027-10-02'],
      ['Rosh Hashana II', '2027-10-03'],
      ['Yom Kippur', '2027-10-11'],
      ['Sukkot I', '2027-10-16'],
      ['Shmini Atzeret', '2027-10-23'],
    ]);
    const days = daysFor(2027, shifted);
    for (const date of [...span('2027-10-02', '2027-10-03'),
                        ...span('2027-10-10', '2027-10-11'),
                        ...span('2027-10-16', '2027-10-23')]) {
      assert(date in days, `${date} should be vacation`);
    }
    for (const date of span('2027-10-04', '2027-10-09')) {
      assert(!(date in days), `${date} should be a school day, got ${days[date]}`);
    }
  },
};

function assert(cond, msg = 'assertion failed') {
  if (!cond) throw new Error(msg);
}

let failures = 0;
for (const [name, fn] of Object.entries(tests)) {
  try {
    fn();
    console.log(`PASS  ${name}`);
  } catch (err) {
    failures += 1;
    console.log(`FAIL  ${name}: ${err.message}`);
  }
}
console.log(`\n${failures ? `${failures} FAILURE(S)` : 'ALL TESTS PASSED'}`);
process.exit(failures ? 1 : 0);
