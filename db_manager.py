"""
db_manager.py - Firestore CRUD operations for the Multi-Tenant School Exam Schedule Platform.

Firestore Collections:
  schools/{school_id}                         - School document (owner_email, name, classes list)
  schools/{school_id}/permissions/{email}     - Teacher permission doc (allowed_classes)
  schools/{school_id}/classes/{class_id}      - Class doc with events array
  schools/{school_id}/payments/{payment_id}   - Payment/charge doc
  global_ministry_data/{exam_code}            - Ministry of Education exam records
  global_holidays/{year}                      - School holidays by year

Setup:
  1. Create a Firebase project at https://console.firebase.google.com/
  2. Enable Firestore in Native mode
  3. Generate a service account key (Project Settings > Service Accounts > Generate new private key)
  4. Save it as firestore-key.json in the project root
  5. Set GOOGLE_APPLICATION_CREDENTIALS or configure in .streamlit/secrets.toml
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# ---------------------------------------------------------------------------
# INITIALISATION
# ---------------------------------------------------------------------------

_db = None

DAY_KEYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "shabbat"]


def _get_db():
    """Lazy-initialise Firestore client.

    Auth priority:
      1. Streamlit secrets [firebase] section (for Streamlit Cloud)
      2. GOOGLE_APPLICATION_CREDENTIALS env var
      3. firestore-key.json file in project root (local dev)
      4. Application Default Credentials (Cloud Run / GCE - no key needed)
    """
    global _db
    if _db is not None:
        return _db

    if not firebase_admin._apps:
        cred = None
        project_id = None

        # 1) Streamlit secrets
        try:
            import streamlit as st
            firebase_cfg = st.secrets.get("firebase", {})
            if firebase_cfg.get("project_id"):
                project_id = firebase_cfg["project_id"]
                cred = credentials.Certificate(dict(firebase_cfg))
        except Exception:
            pass

        # 2) Explicit key file (check common naming mistakes too)
        if cred is None:
            key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
            candidates = [key_path] if key_path else []
            candidates += [
                str(Path(__file__).parent / "firestore-key.json"),
                str(Path(__file__).parent / "firestore-key.json.json"),
                str(Path(__file__).parent / "serviceAccountKey.json"),
            ]
            for path in candidates:
                if path and Path(path).exists():
                    cred = credentials.Certificate(path)
                    # Extract project_id from the key file
                    try:
                        with open(path, encoding="utf-8") as f:
                            key_data = json.load(f)
                            project_id = key_data.get("project_id", project_id)
                    except Exception:
                        pass
                    break

        # 3) Application Default Credentials (Cloud Run auto-provides these)
        if cred is None:
            try:
                cred = credentials.ApplicationDefault()
            except Exception:
                raise RuntimeError(
                    "Firebase credentials not found. Place firestore-key.json "
                    "in the project root, or set GOOGLE_APPLICATION_CREDENTIALS, "
                    "or configure [firebase] in .streamlit/secrets.toml"
                )

        # Extract project_id from credential if not already set
        if not project_id and hasattr(cred, 'project_id'):
            project_id = cred.project_id

        # Initialize with explicit project ID
        options = {}
        if project_id:
            options['projectId'] = project_id
        firebase_admin.initialize_app(cred, options)

    _db = firestore.client()
    return _db


def verify_firebase_token(id_token: str) -> dict | None:
    """Verify a Firebase ID token and return the decoded claims.

    Ensures the Admin SDK is initialised before verification.
    Returns dict with 'uid', 'email', etc. or None on failure.
    """
    _get_db()  # ensure firebase_admin app is initialised
    try:
        return firebase_auth.verify_id_token(id_token)
    except Exception:
        return None


# ===================================================================
# SCHOOLS
# ===================================================================

def create_school(school_id: str, owner_email: str, school_name: str, classes: list[str] | None = None):
    """Create a new school document."""
    db = _get_db()
    if classes is None:
        classes = ["יא 1", "יא 2", "יא 3"]
    doc_ref = db.collection("schools").document(school_id)
    doc_ref.set({
        "owner_email": owner_email.lower(),
        "name": school_name,
        "classes": classes,
        "year": "",
        "parashat_hashavua": {},
        "subscription_status": "trial",
        "subscription_expiry": "",
        "created_at": firestore.SERVER_TIMESTAMP,
    })
    # Initialise empty class docs
    for cls in classes:
        doc_ref.collection("classes").document(cls).set({"events": []})
    # Owner gets full permission
    doc_ref.collection("permissions").document(owner_email.lower()).set({
        "email": owner_email.lower(),
        "role": "director",
        "allowed_classes": classes,
    })
    # Sync lookup doc
    _sync_user_school(owner_email, school_id, "director", classes)
    return school_id


def get_school(school_id: str) -> dict | None:
    """Fetch a school document."""
    db = _get_db()
    doc = db.collection("schools").document(school_id).get()
    if doc.exists:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        return data
    return None


def update_school(school_id: str, updates: dict):
    """Partial update on school document."""
    db = _get_db()
    db.collection("schools").document(school_id).update(updates)


def set_subscription(school_id: str, status: str, expiry_date: str):
    """Set the school's annual subscription status.

    Args:
        status: 'trial' | 'active' | 'expired'
        expiry_date: YYYY-MM-DD when the subscription ends.
    """
    db = _get_db()
    db.collection("schools").document(school_id).update({
        "subscription_status": status,
        "subscription_expiry": expiry_date,
    })


def check_subscription(school_id: str) -> dict:
    """Check if a school's subscription is valid."""
    school = get_school(school_id)
    if not school:
        return {"valid": False, "status": "unknown"}
    status = school.get("subscription_status", "trial")
    expiry = school.get("subscription_expiry", "")
    if status == "trial":
        return {"valid": True, "status": "trial", "expiry": expiry}
    if status == "active" and expiry:
        from datetime import datetime
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            if exp_date >= datetime.now().date():
                return {"valid": True, "status": "active", "expiry": expiry}
            else:
                return {"valid": False, "status": "expired", "expiry": expiry}
        except Exception:
            pass
    return {"valid": False, "status": status, "expiry": expiry}


def _sync_user_school(email: str, school_id: str, role: str, allowed_classes: list[str]):
    """Maintain a top-level user_schools/{email} doc for fast lookups.

    This avoids collection group queries (which require Firestore indexes).
    Structure: user_schools/{email} -> { schools: { school_id: {role, allowed_classes} } }
    """
    db = _get_db()
    doc_ref = db.collection("user_schools").document(email.lower())
    user_doc = doc_ref.get()
    schools_map = _get_user_schools_map(user_doc)

    # Cleanup old field-path-style nesting for dotted IDs, then write safe map key.
    _remove_legacy_nested_school_key(schools_map, school_id)
    schools_map[school_id] = {
        "role": role,
        "allowed_classes": allowed_classes,
    }
    doc_ref.set({"schools": schools_map}, merge=True)


def _remove_user_school(email: str, school_id: str):
    """Remove a school from a user's lookup doc."""
    db = _get_db()
    doc_ref = db.collection("user_schools").document(email.lower())
    user_doc = doc_ref.get()
    if not user_doc.exists:
        return

    schools_map = _get_user_schools_map(user_doc)
    if school_id in schools_map:
        del schools_map[school_id]
    _remove_legacy_nested_school_key(schools_map, school_id)

    doc_ref.set({"schools": schools_map}, merge=True)


def _get_user_schools_map(user_doc) -> dict:
    """Extract the schools map from user_schools/{email} doc."""
    if not user_doc.exists:
        return {}
    data = user_doc.to_dict() or {}
    schools_map = data.get("schools", {})
    return schools_map if isinstance(schools_map, dict) else {}


def _iter_school_lookup_entries(schools_map: dict):
    """Yield (school_id, info) entries and tolerate legacy dotted-ID nesting."""
    stack = [("", schools_map)]
    while stack:
        prefix, node = stack.pop()
        if not isinstance(node, dict):
            continue

        # Leaf entry: expected permission payload.
        if "role" in node or "allowed_classes" in node:
            if prefix:
                yield prefix, node
            continue

        for key, value in node.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                stack.append((child_prefix, value))


def _remove_legacy_nested_school_key(schools_map: dict, school_id: str):
    """Best-effort cleanup of old nested maps created from dotted field paths."""
    parts = school_id.split(".")
    if len(parts) <= 1:
        return

    parents = []
    cursor = schools_map
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor or not isinstance(cursor[part], dict):
            return
        parents.append((cursor, part))
        cursor = cursor[part]

    if isinstance(cursor, dict) and parts[-1] in cursor:
        del cursor[parts[-1]]

    # Prune empty dict branches.
    for parent, key in reversed(parents):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            del parent[key]
        else:
            break


def _fallback_permissions_lookup(email_lower: str) -> list[tuple[str, dict]]:
    """Fallback lookup for legacy/missing user_schools entries.

    1) Try collection-group query (fast path).
    2) If indexing/policy blocks that query, fall back to index-free scan.
    """
    db = _get_db()
    entries: list[tuple[str, dict]] = []

    # Fast path (may fail if collection-group indexing is disabled/restricted).
    try:
        docs = db.collection_group("permissions").where(
            filter=FieldFilter("email", "==", email_lower)
        ).stream()
        for doc in docs:
            school_ref = doc.reference.parent.parent
            if not school_ref:
                continue
            info = doc.to_dict() or {}
            entries.append((school_ref.id, info))
        return entries
    except Exception:
        entries = []

    # Index-free path: iterate schools and read permissions/{email} directly.
    try:
        school_docs = db.collection("schools").stream()
    except Exception:
        return entries

    for school_doc in school_docs:
        school_id = school_doc.id
        try:
            perm_doc = db.collection("schools").document(school_id) \
                .collection("permissions").document(email_lower).get()
        except Exception:
            continue
        if not perm_doc.exists:
            continue
        info = perm_doc.to_dict() or {}
        entries.append((school_id, info))

    return entries


def list_schools_for_user(email: str) -> list[dict]:
    """Return all schools where the user has access (owner or teacher)."""
    db = _get_db()
    email_lower = email.lower()
    results = []
    seen_ids = set()

    # 1) Check schools where user is owner
    owner_query = db.collection("schools").where(filter=FieldFilter("owner_email", "==", email_lower)).stream()
    for doc in owner_query:
        d = doc.to_dict() or {}
        d["id"] = doc.id
        d["user_role"] = "director"
        results.append(d)
        seen_ids.add(doc.id)

    # 2) Check user_schools lookup doc (for teacher invitations)
    lookup_hits = 0
    user_doc = db.collection("user_schools").document(email_lower).get()
    if user_doc.exists:
        schools_map = _get_user_schools_map(user_doc)
        for school_id, info in _iter_school_lookup_entries(schools_map):
            if school_id in seen_ids:
                continue
            school_doc = db.collection("schools").document(school_id).get()
            if school_doc.exists:
                d = school_doc.to_dict() or {}
                d["id"] = school_doc.id
                d["user_role"] = info.get("role", "teacher")
                allowed_classes = info.get("allowed_classes", [])
                d["allowed_classes"] = allowed_classes if isinstance(allowed_classes, list) else []
                results.append(d)
                seen_ids.add(school_id)
                lookup_hits += 1

    # 3) Legacy/backfill path: permissions collection-group lookup.
    # This heals users invited before lookup-map fixes.
    if lookup_hits == 0:
        for school_id, info in _fallback_permissions_lookup(email_lower):
            if school_id in seen_ids:
                continue
            school_doc = db.collection("schools").document(school_id).get()
            if not school_doc.exists:
                continue
            d = school_doc.to_dict() or {}
            d["id"] = school_doc.id
            role = info.get("role", "teacher")
            allowed_classes = info.get("allowed_classes", [])
            allowed_classes = allowed_classes if isinstance(allowed_classes, list) else []
            d["user_role"] = role
            d["allowed_classes"] = allowed_classes
            results.append(d)
            seen_ids.add(school_id)

            # Rebuild top-level lookup for future logins.
            _sync_user_school(email_lower, school_id, role, allowed_classes)

    return results


def add_class_to_school(school_id: str, class_name: str):
    """Add a new class to the school."""
    db = _get_db()
    school_ref = db.collection("schools").document(school_id)
    school_ref.update({"classes": firestore.ArrayUnion([class_name])})
    school_ref.collection("classes").document(class_name).set({"events": []}, merge=True)


# ===================================================================
# PERMISSIONS (Staff Management)
# ===================================================================

def set_teacher_permission(school_id: str, teacher_email: str, allowed_classes: list[str], role: str = "teacher"):
    """Grant a user (teacher/director) access to specific classes."""
    db = _get_db()
    db.collection("schools").document(school_id) \
        .collection("permissions").document(teacher_email.lower()).set({
            "email": teacher_email.lower(),
            "role": role,
            "allowed_classes": allowed_classes,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })
    _sync_user_school(teacher_email, school_id, role, allowed_classes)


def remove_teacher_permission(school_id: str, teacher_email: str):
    """Revoke teacher access."""
    db = _get_db()
    db.collection("schools").document(school_id) \
        .collection("permissions").document(teacher_email.lower()).delete()
    _remove_user_school(teacher_email, school_id)


def get_permissions(school_id: str) -> dict:
    """Return dict of {email: {role, allowed_classes}} for a school."""
    db = _get_db()
    perms = {}
    docs = db.collection("schools").document(school_id) \
        .collection("permissions").stream()
    for doc in docs:
        perms[doc.id] = doc.to_dict()
    return perms


def get_user_permission(school_id: str, email: str) -> dict | None:
    """Get a specific user's permission for a school."""
    db = _get_db()
    doc = db.collection("schools").document(school_id) \
        .collection("permissions").document(email.lower()).get()
    if doc.exists:
        return doc.to_dict()
    return None


# ===================================================================
# CLASS EVENTS (Schedule Data)
# ===================================================================

def get_class_events(school_id: str, class_name: str) -> list[dict]:
    """Get all events for a class."""
    db = _get_db()
    doc = db.collection("schools").document(school_id) \
        .collection("classes").document(class_name).get()
    if doc.exists:
        return doc.to_dict().get("events", [])
    return []


def save_class_events(school_id: str, class_name: str, events: list[dict]):
    """Overwrite events for a class."""
    db = _get_db()
    db.collection("schools").document(school_id) \
        .collection("classes").document(class_name).set({"events": events})


def add_event(school_id: str, class_name: str, event: dict):
    """Append a single event to a class."""
    db = _get_db()
    db.collection("schools").document(school_id) \
        .collection("classes").document(class_name).update({
            "events": firestore.ArrayUnion([event])
        })


def remove_event(school_id: str, class_name: str, event: dict):
    """Remove a single event from a class."""
    db = _get_db()
    db.collection("schools").document(school_id) \
        .collection("classes").document(class_name).update({
            "events": firestore.ArrayRemove([event])
        })

# ===================================================================
# SCHEDULE WEEK STRUCTURE
# ===================================================================

@st.cache_data(ttl=30, show_spinner=False)
def get_schedule(school_id: str) -> dict:
    """Get the full schedule structure (weeks + metadata) for a school."""
    school = get_school(school_id)
    if not school:
        return {"classes": [], "year": "", "weeks": [], "parashat_hashavua": {}}

    db = _get_db()
    weeks_doc = db.collection("schools").document(school_id) \
        .collection("schedule_meta").document("weeks").get()
    weeks = []
    if weeks_doc.exists:
        weeks = weeks_doc.to_dict().get("weeks", [])

    return {
        "classes": school.get("classes", []),
        "year": school.get("year", ""),
        "weeks": weeks,
        "parashat_hashavua": school.get("parashat_hashavua", {}),
    }


def save_schedule(school_id: str, schedule_data: dict):
    """Save the full schedule (weeks + metadata)."""
    # Clear cached schedule so next read picks up fresh data
    get_schedule.clear()
    db = _get_db()
    school_ref = db.collection("schools").document(school_id)
    school_ref.update({
        "classes": schedule_data.get("classes", []),
        "year": schedule_data.get("year", ""),
        "parashat_hashavua": schedule_data.get("parashat_hashavua", {}),
    })
    # Weeks stored in sub-doc to avoid 1MB doc limit
    school_ref.collection("schedule_meta").document("weeks").set({
        "weeks": schedule_data.get("weeks", []),
    })


# ===================================================================
# GLOBAL MINISTRY DATA
# ===================================================================

def get_ministry_exams() -> list[dict]:
    """Fetch all ministry exam records."""
    db = _get_db()
    exams = []
    docs = db.collection("global_ministry_data").stream()
    for doc in docs:
        d = doc.to_dict() or {}
        d["code"] = doc.id
        exams.append(d)
    return exams


def get_ministry_exam(code: str) -> dict | None:
    """Fetch a single ministry exam by code."""
    db = _get_db()
    doc = db.collection("global_ministry_data").document(str(code)).get()
    if doc.exists:
        d = doc.to_dict() or {}
        d["code"] = doc.id
        return d
    return None


def save_ministry_exams(exams: list[dict], moed: str = "", source: str = ""):
    """Bulk upsert ministry exams. Also stores metadata."""
    db = _get_db()
    batch = db.batch()
    meta_ref = db.collection("global_ministry_data").document("_metadata")
    batch.set(meta_ref, {
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "moed": moed,
        "source": source,
        "count": len(exams),
    })
    for exam in exams:
        code = str(exam.get("code", ""))
        if not code or code == "_metadata":
            continue
        ref = db.collection("global_ministry_data").document(code)
        batch.set(ref, {
            "name": exam.get("name", ""),
            "date": exam.get("date", ""),
            "start_time": exam.get("start_time", ""),
            "end_time": exam.get("end_time", ""),
        })
    batch.commit()


def get_ministry_meta() -> dict:
    """Get ministry data metadata (last_updated, moed, count)."""
    db = _get_db()
    doc = db.collection("global_ministry_data").document("_metadata").get()
    if doc.exists:
        return doc.to_dict()
    return {}


def search_ministry_exams(query: str) -> list[dict]:
    """Search ministry exams by code or name substring."""
    query = query.strip()
    if not query:
        return []
    all_exams = get_ministry_exams()
    results = []
    for exam in all_exams:
        if exam.get("code") == "_metadata":
            continue
        if query == exam.get("code", ""):
            results.append(exam)
        elif query.lower() in exam.get("name", "").lower():
            results.append(exam)
    return results


# ===================================================================
# GLOBAL HOLIDAYS
# ===================================================================

def get_holidays(year: str) -> dict:
    """Get holidays for a given year."""
    db = _get_db()
    doc = db.collection("global_holidays").document(str(year)).get()
    if doc.exists:
        return doc.to_dict()
    return {}


def save_holidays(year: str, data: dict):
    """Save holidays for a given year."""
    db = _get_db()
    db.collection("global_holidays").document(str(year)).set(data)


# ===================================================================
# PAYMENTS
# ===================================================================
#
# Simple model:
#   - Schools pay an annual subscription (stored on school doc).
#   - Directors create charges for students (field trips, etc.).
#   - Parents see charges via the permanent public link - NO login required.
#
# Firestore:
#   schools/{school_id}/payments/{auto_id}
#     - description, amount, class, due_date, created_by, created_at
#

def get_payments(school_id: str) -> list[dict]:
    """Get all charge records for a school."""
    db = _get_db()
    payments = []
    docs = db.collection("schools").document(school_id) \
        .collection("payments").order_by("created_at", direction=firestore.Query.DESCENDING).stream()
    for doc in docs:
        d = doc.to_dict() or {}
        d["id"] = doc.id
        payments.append(d)
    return payments


def get_payments_for_class(school_id: str, class_name: str) -> list[dict]:
    """Get charges relevant to a specific class (or 'all')."""
    all_payments = get_payments(school_id)
    return [p for p in all_payments if p.get("class") in (class_name, "כולם")]


def add_payment(school_id: str, charge: dict) -> str:
    """Add a charge/payment record. Returns the doc ID."""
    db = _get_db()
    charge["created_at"] = firestore.SERVER_TIMESTAMP
    _, ref = db.collection("schools").document(school_id) \
        .collection("payments").add(charge)
    return ref.id


def delete_payment(school_id: str, payment_id: str):
    """Delete a payment record."""
    db = _get_db()
    db.collection("schools").document(school_id) \
        .collection("payments").document(payment_id).delete()


# ===================================================================
# SEED / MIGRATION HELPERS
# ===================================================================

def seed_ministry_from_local_json(json_path: str):
    """One-time migration: load ministry_exams_database.json into Firestore."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    exams = data.get("exams", [])
    save_ministry_exams(
        exams,
        moed=data.get("moed", ""),
        source=data.get("source", ""),
    )
    return len(exams)


def seed_holidays_from_local_json(json_path: str):
    """One-time migration: load school_holidays.json into Firestore."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    for year_key, year_data in data.items():
        save_holidays(year_key, year_data)
    return list(data.keys())


def migrate_schedule_to_firestore(school_id: str, json_path: str):
    """One-time migration: load schedule_data.json into Firestore for a school."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    save_schedule(school_id, data)
    # Also extract per-class events from the weeks structure
    classes = data.get("classes", [])
    for cls in classes:
        events = []
        for wk in data.get("weeks", []):
            for dk in DAY_KEYS:
                for ev in wk["days"].get(dk, []):
                    if ev.get("class") in (cls, "all"):
                        enriched = dict(ev)
                        enriched["week_start"] = wk["start_date"]
                        enriched["day_key"] = dk
                        events.append(enriched)
        save_class_events(school_id, cls, events)
    return len(classes)
