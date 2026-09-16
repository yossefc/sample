/**
 * Firestore access + calendar shaping.
 *
 * Reads and writes the *same* documents as the existing Python app, so both can
 * run against one database during the transition:
 *   schools/{id}                        { name, owner_email, classes[] }
 *   schools/{id}/schedule_meta/weeks    { weeks[], rev }
 *   schools/{id}/permissions/{email}    { role, allowed_classes[] }
 *   user_schools/{email}                { schools: { id: {role, allowed_classes} } }
 */

import {
  collection, collectionGroup, deleteDoc, doc, getDoc, getDocs, query,
  runTransaction, setDoc, where, writeBatch,
} from 'firebase/firestore';
import { db } from './firebase.js';
import { DAY_KEYS } from './constants.js';
import { addDays, fmtDate } from './vacationRules.js';

const emptyDays = () => Object.fromEntries(DAY_KEYS.map((k) => [k, []]));

/**
 * Schools the signed-in user can open.
 *
 * Looks in both places, because they cover different people: a director is tied
 * to their school by `owner_email` on the school document, while an invited
 * teacher is tied by the per-user invitation index. Relying on the index alone
 * leaves a director with no school when it was never written for them.
 *
 * Returns { schools, problems } — problems carries read errors instead of
 * swallowing them, so "no school" can be told apart from "access denied".
 */
export async function loadUserSchools(email) {
  const key = String(email || '').toLowerCase();
  if (!key) return { schools: [], problems: [] };

  const found = new Map();
  const problems = [];

  // 1) Schools this user owns.
  try {
    const owned = await getDocs(
      query(collection(db, 'schools'), where('owner_email', '==', key)),
    );
    owned.docs.forEach((d) => {
      found.set(d.id, { id: d.id, role: 'director', allowedClasses: [] });
    });
  } catch (err) {
    problems.push(`בעלות: ${err?.code || err?.message}`);
  }

  // 2) Schools that invited them. A collection-group query over permission
  //    documents means a director only ever writes inside their own school —
  //    no writing into a document owned by the invited teacher.
  try {
    const invited = await getDocs(
      query(collectionGroup(db, 'permissions'), where('email', '==', key)),
    );
    invited.docs.forEach((d) => {
      const id = d.ref.parent.parent?.id;
      if (!id || found.has(id)) return;
      const info = d.data() ?? {};
      found.set(id, {
        id,
        role: info.role ?? 'teacher',
        allowedClasses: Array.isArray(info.allowed_classes) ? info.allowed_classes : [],
      });
    });
  } catch (err) {
    problems.push(`הרשאות: ${err?.code || err?.message}`);
  }

  // 3) Legacy per-user index, kept so anything created by the older app is found.
  try {
    const snap = await getDoc(doc(db, 'user_schools', key));
    if (snap.exists()) {
      for (const [id, info] of Object.entries(snap.data()?.schools ?? {})) {
        if (found.has(id)) continue;
        found.set(id, {
          id,
          role: info?.role ?? 'teacher',
          allowedClasses: Array.isArray(info?.allowed_classes) ? info.allowed_classes : [],
        });
      }
    }
  } catch {
    /* the index is optional — the two lookups above are the real ones */
  }

  const schools = [];
  for (const entry of found.values()) {
    try {
      const school = await loadSchool(entry.id);
      if (school) schools.push({ ...school, role: entry.role, allowedClasses: entry.allowedClasses });
    } catch (err) {
      problems.push(`${entry.id}: ${err?.code || err?.message}`);
    }
  }
  return { schools, problems };
}

export async function loadSchool(schoolId) {
  const snap = await getDoc(doc(db, 'schools', schoolId));
  if (!snap.exists()) return null;
  const d = snap.data() ?? {};
  return {
    id: snap.id,
    name: d.name ?? schoolId,
    ownerEmail: String(d.owner_email ?? '').toLowerCase(),
    classes: Array.isArray(d.classes) ? d.classes : [],
    year: d.year ?? '',
    parashot: d.parashat_hashavua && typeof d.parashat_hashavua === 'object' ? d.parashat_hashavua : {},
  };
}

/** Merge year label / parashot / classes into the school document. */
export async function saveSchoolMeta(schoolId, { year, parashot, classes } = {}) {
  const patch = {};
  if (year != null) patch.year = year;
  if (parashot) patch.parashat_hashavua = parashot;
  if (classes) patch.classes = classes;
  await setDoc(doc(db, 'schools', schoolId), patch, { merge: true });
}

export async function loadPermissions(schoolId) {
  const snap = await getDocs(collection(db, 'schools', schoolId, 'permissions'));
  return snap.docs.map((p) => ({ email: p.id, ...(p.data() ?? {}) }));
}

/** Invite someone, or change what they may see. Directors only (enforced by rules). */
export async function setPermission(schoolId, email, { role = 'teacher', allowedClasses = [] } = {}) {
  const key = String(email || '').trim().toLowerCase();
  if (!key) throw new Error('חסר אימייל');
  await setDoc(doc(db, 'schools', schoolId, 'permissions', key), {
    email: key,
    role,
    allowed_classes: allowedClasses,
    updated_at: new Date().toISOString(),
  });
}

/** Revoke access. */
export async function removePermission(schoolId, email) {
  await deleteDoc(doc(db, 'schools', schoolId, 'permissions', String(email).toLowerCase()));
}

/** Basic sanity check before writing an invitation. */
export const isValidEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value ?? '').trim());

/** The stored weeks array plus its revision (used for optimistic concurrency). */
export async function loadWeeks(schoolId) {
  const snap = await getDoc(doc(db, 'schools', schoolId, 'schedule_meta', 'weeks'));
  if (!snap.exists()) return { weeks: [], rev: 0 };
  const d = snap.data() ?? {};
  return { weeks: Array.isArray(d.weeks) ? d.weeks : [], rev: Number(d.rev ?? 0) };
}

/**
 * Persist weeks, refusing the write if someone else saved since we loaded.
 * Mirrors save_schedule()'s optimistic concurrency in the Python app.
 */
export async function saveWeeks(schoolId, weeks, expectedRev) {
  const ref = doc(db, 'schools', schoolId, 'schedule_meta', 'weeks');
  return runTransaction(db, async (tx) => {
    const snap = await tx.get(ref);
    const currentRev = snap.exists() ? Number(snap.data()?.rev ?? 0) : 0;
    if (expectedRev != null && Number(expectedRev) !== currentRev) {
      const err = new Error('schedule changed since load');
      err.code = 'schedule/conflict';
      throw err;
    }
    const nextRev = currentRev + 1;
    tx.set(ref, { weeks, rev: nextRev });
    return nextRev;
  });
}

/** Build the empty week scaffold for a school year starting in September. */
export function buildYearWeeks(startYear) {
  const sep1 = new Date(Date.UTC(startYear, 8, 1));
  // Back up to the Sunday on or before September 1st.
  const firstSunday = addDays(sep1, -sep1.getUTCDay());
  const lastDay = Date.UTC(startYear + 1, 7, 31);

  const weeks = [];
  for (let cur = firstSunday; cur.getTime() <= lastDay; cur = addDays(cur, 7)) {
    const end = addDays(cur, 6);
    const sameMonth = cur.getUTCMonth() === end.getUTCMonth();
    weeks.push({
      date_range: sameMonth
        ? `${cur.getUTCDate()}-${end.getUTCDate()}.${cur.getUTCMonth() + 1}`
        : `${cur.getUTCDate()}.${cur.getUTCMonth() + 1}-${end.getUTCDate()}.${end.getUTCMonth() + 1}`,
      start_date: fmtDate(cur),
      days: emptyDays(),
    });
  }
  return weeks;
}

/** { 'YYYY-MM-DD': events[] } for fast lookup while rendering. */
export function weeksToDayMap(weeks) {
  const map = {};
  for (const wk of weeks || []) {
    const start = wk?.start_date ? new Date(`${wk.start_date}T00:00:00Z`) : null;
    if (!start || Number.isNaN(start.getTime())) continue;
    DAY_KEYS.forEach((dk, i) => {
      const events = wk?.days?.[dk];
      if (Array.isArray(events) && events.length) {
        map[fmtDate(addDays(start, i))] = events;
      }
    });
  }
  return map;
}

/** Locate a date inside the weeks array: [weekIndex, dayKey] or null. */
export function findDaySlot(weeks, dateStr) {
  const target = new Date(`${dateStr}T00:00:00Z`).getTime();
  if (Number.isNaN(target)) return null;
  for (let wi = 0; wi < (weeks?.length ?? 0); wi += 1) {
    const start = new Date(`${weeks[wi]?.start_date}T00:00:00Z`);
    if (Number.isNaN(start.getTime())) continue;
    const diff = Math.round((target - start.getTime()) / 86400000);
    if (diff >= 0 && diff < 7) return [wi, DAY_KEYS[diff]];
  }
  return null;
}

/** Return a new weeks array with `events` set on `dateStr` (immutably). */
export function withDayEvents(weeks, dateStr, events) {
  const slot = findDaySlot(weeks, dateStr);
  if (!slot) return weeks;
  const [wi, dk] = slot;
  return weeks.map((wk, i) => (
    i === wi ? { ...wk, days: { ...wk.days, [dk]: events } } : wk
  ));
}

/** Paint generated holiday + vacation markers onto an empty week scaffold. */
export function applySystemDays(weeks, holidays, vacationDays) {
  const out = weeks.map((wk) => ({ ...wk, days: { ...wk.days } }));

  const push = (dateStr, event) => {
    const slot = findDaySlot(out, dateStr);
    if (!slot) return;
    const [wi, dk] = slot;
    const cell = out[wi].days[dk] ?? [];
    if (cell.some((e) => e.text === event.text)) return; // no duplicates
    out[wi].days[dk] = [...cell, event];
  };

  for (const h of holidays || []) {
    if (!h?.date) continue;
    push(String(h.date).slice(0, 10), {
      text: h.text ?? '', type: h.type ?? 'holiday', class: 'all',
    });
  }
  for (const [dateStr, labels] of Object.entries(vacationDays || {})) {
    for (const label of labels) {
      push(dateStr, { text: label, type: 'vacation', class: 'all' });
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Ministry (bagrut) exams — ports of the Python import helpers.
// ---------------------------------------------------------------------------

/** "9:5" / "09:05:00" / Date -> "09:05"; anything else passes through. */
export function normalizeExamTime(value) {
  if (value == null) return '';
  const raw = String(value).trim();
  if (!raw) return '';
  const m = /^(\d{1,2}):(\d{2})(?::\d{2})?$/.exec(raw);
  return m ? `${m[1].padStart(2, '0')}:${m[2]}` : raw;
}

/** Display label for a bagrut event, e.g. "בגרות מתמטיקה (035806) 09:00-12:00". */
export function buildBagrutLabel(exam) {
  const start = normalizeExamTime(exam?.start_time);
  const end = normalizeExamTime(exam?.end_time);
  let base = `בגרות ${exam?.name ?? ''}`.trim();
  if (exam?.code) base += ` (${exam.code})`;
  if (start && end) base += ` ${start}-${end}`;
  return base;
}

/**
 * The school's ministry exam list plus its metadata. Falls back to the legacy
 * shared collection while the school has no copy of its own.
 */
export async function loadMinistryExams(schoolId) {
  const read = async (col) => {
    const snap = await getDocs(col);
    const exams = [];
    let meta = {};
    snap.docs.forEach((d) => {
      if (d.id === '_metadata') meta = d.data() ?? {};
      else exams.push({ code: d.id, ...(d.data() ?? {}) });
    });
    return { exams, meta };
  };
  const own = await read(collection(db, 'schools', schoolId, 'ministry_data'));
  if (own.exams.length) return own;
  return read(collection(db, 'global_ministry_data'));
}

/** Does this exam date fall inside the school year starting in `startYear`? */
export function inSchoolYear(dateStr, startYear) {
  const t = Date.parse(`${String(dateStr ?? '').slice(0, 10)}T00:00:00Z`);
  return Number.isFinite(t)
    && t >= Date.UTC(startYear, 8, 1)
    && t <= Date.UTC(startYear + 1, 7, 31);
}

/** How many of the loaded exams belong to this school year. */
export function ministryCoverage(exams, startYear) {
  const list = exams || [];
  return { total: list.length, inYear: list.filter((e) => inSchoolYear(e.date, startYear)).length };
}

/**
 * Place a ministry exam in the schedule for a class.
 *
 * The schedule's own date range is the test — not an equality on the year.
 * A winter session legitimately starts in December of the *first* calendar year
 * (תשפ"ז runs 28/12/2026 → 09/02/2027), so requiring startYear+1 would have
 * rejected half of it; while a previous session's dates fall outside the
 * schedule entirely and are still refused.
 *
 * Returns { weeks, ok, message }.
 */
export function importExamToWeeks(weeks, exam, cls) {
  const date = String(exam?.date ?? '').slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return { weeks, ok: false, message: 'תאריך לא תקין' };

  const slot = findDaySlot(weeks, date);
  if (!slot) {
    return { weeks, ok: false, message: `${date} מחוץ לשנת הלוח — כנראה מועד של שנה אחרת.` };
  }
  const [wi, dk] = slot;
  const cell = weeks[wi].days[dk] ?? [];
  if (cell.some((e) => e.exam_code === exam.code && e.class === cls)) {
    return { weeks, ok: false, message: 'הבגרות כבר קיימת בלוח בתאריך זה' };
  }
  const event = {
    text: buildBagrutLabel(exam),
    type: 'bagrut',
    class: cls,
    exam_code: exam.code,
    start_time: normalizeExamTime(exam.start_time),
    end_time: normalizeExamTime(exam.end_time),
  };
  return { weeks: withDayEvents(weeks, date, [...cell, event]), ok: true, message: '' };
}

/** Replace the school's ministry exam list (chunked to stay within batch limits). */
export async function saveMinistryExams(schoolId, exams, moed) {
  const col = collection(db, 'schools', schoolId, 'ministry_data');
  const chunkSize = 400;
  for (let i = 0; i < exams.length; i += chunkSize) {
    const batch = writeBatch(db);
    for (const exam of exams.slice(i, i + chunkSize)) {
      batch.set(doc(col, String(exam.code)), {
        name: exam.name ?? '',
        date: exam.date ?? '',
        start_time: exam.start_time ?? '',
        end_time: exam.end_time ?? '',
      });
    }
    await batch.commit();
  }
  const meta = writeBatch(db);
  meta.set(doc(col, '_metadata'), {
    last_updated: new Date().toISOString().slice(0, 10),
    moed: moed ?? '',
    source: 'העלאת קובץ משרד החינוך',
    count: exams.length,
  });
  await meta.commit();
}
