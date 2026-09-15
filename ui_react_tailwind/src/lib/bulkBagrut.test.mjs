/** Run: node src/lib/bulkBagrut.test.mjs */
import { parseBagrutLines, parseDate, parseTimes, rowToEvent } from './bulkBagrut.js';

const tests = {
  'parses the draft formats a school would type'() {
    const { rows, errors } = parseBagrutLines([
      'מתמטיקה 35582 | 25/04/2027 | 09:00-12:30',
      'אנגלית | 31.5.2027',
      'תנך | 2027-05-12 | 9:00',
      '',
      '# הערה',
    ].join('\n'), 2027);

    assert(errors.length === 0, `unexpected errors: ${errors}`);
    assert(rows.length === 3, `expected 3 rows, got ${rows.length}`);
    assertEq(rows[0].date, '2027-04-25');
    assertEq(rows[0].start, '09:00');
    assertEq(rows[0].end, '12:30');
    assertEq(rows[1].date, '2027-05-31');
    assertEq(rows[1].start, '');
    assertEq(rows[2].date, '2027-05-12');
    assertEq(rows[2].start, '09:00');
  },

  'falls back to the schedule year when none is typed'() {
    const { rows } = parseBagrutLines('היסטוריה | 3/6', 2027);
    assertEq(rows[0].date, '2027-06-03');
  },

  'accepts tab and wide-space separators'() {
    const { rows } = parseBagrutLines('ביולוגיה\t12/06/2027\t09:00-12:00', 2027);
    assertEq(rows[0].name, 'ביולוגיה');
    assertEq(rows[0].date, '2027-06-12');
    const spaced = parseBagrutLines('פיזיקה    12/06/2027', 2027);
    assertEq(spaced.rows[0].name, 'פיזיקה');
  },

  'reports a line it cannot read instead of dropping it silently'() {
    const { rows, errors } = parseBagrutLines('מקצוע בלי תאריך', 2027);
    assert(rows.length === 0);
    assert(errors.length === 1 && errors[0].includes('שורה 1'), errors.join());
  },

  'builds the stored event shape'() {
    const ev = rowToEvent({ name: 'מתמטיקה', date: '2027-04-25', start: '09:00', end: '12:30' }, 'י');
    assertEq(ev.type, 'bagrut');
    assertEq(ev.class, 'י');
    assertEq(ev.text, 'בגרות מתמטיקה 09:00-12:30');
    assertEq(ev.start_time, '09:00');
  },

  'date and time helpers reject junk'() {
    assert(parseDate('הבלים', 2027) === null);
    assert(parseDate('45/13/2027', 2027) === null);
    assertEq(parseTimes('').start, '');
  },
};

function assert(cond, msg = 'assertion failed') { if (!cond) throw new Error(msg); }
function assertEq(a, b) { if (a !== b) throw new Error(`expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`); }

let failures = 0;
for (const [name, fn] of Object.entries(tests)) {
  try { fn(); console.log(`PASS  ${name}`); }
  catch (err) { failures += 1; console.log(`FAIL  ${name}: ${err.message}`); }
}
console.log(`\n${failures ? `${failures} FAILURE(S)` : 'ALL TESTS PASSED'}`);
process.exit(failures ? 1 : 0);
