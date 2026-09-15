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
  collection, doc, getDoc, getDocs, runTransaction,
} from 'firebase/firestore';
import { db } from './firebase.js';
import { DAY_KEYS } from './constants.js';
import { addDays, fmtDate } from './vacationRules.js';

const emptyDays = () => Object.fromEntries(DAY_KEYS.map((k) => [k, []]));

/** Schools the signed-in user can open (owned, plus those they were invited to). */
export async function loadUserSchools(email) {
  const key = String(email || '').toLowerCase();
  if (!key) return [];

  const found = new Map();

  // Invitations are indexed per user, which is the only lookup a plain teacher
  // is allowed to make by the security rules.
  try {
    const snap = await getDoc(doc(db, 'user_schools', key));
    if (snap.exists()) {
      const schools = snap.data()?.schools ?? {};
      for (const [id, info] of Object.entries(schools)) {
        found.set(id, {
          id,
          role: info?.role ?? 'teacher',
          allowedClasses: Array.isArray(info?.allowed_classes) ? info.allowed_classes : [],
        });
      }
    }
  } catch {
    /* no invitations, or not readable — fall through */
  }

  const out = [];
  for (const entry of found.values()) {
    const school = await loadSchool(entry.id);
    if (school) out.push({ ...entry, ...school });
  }
  return out;
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
  };
}

export async function loadPermissions(schoolId) {
  const snap = await getDocs(collection(db, 'schools', schoolId, 'permissions'));
  return snap.docs.map((p) => ({ email: p.id, ...(p.data() ?? {}) }));
}

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
