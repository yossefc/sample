"""
auth_manager.py - Authentication & Role Management for Multi-Tenant School Platform.

Supports three flows:
  1. Director: Sign up / Log in -> Create or manage schools.
  2. Teacher:  Log in -> System checks Firestore permissions -> Edit assigned classes.
  3. Parent/Student: Public link with ?school_id=X&class=Y&mode=view -> Read-only, no login.

Uses Streamlit's built-in OIDC (Google) for authentication.
Falls back to simple email/password form when OIDC is not configured.
"""

import streamlit as st
from db_manager import (
    get_school,
    get_user_permission,
    list_schools_for_user,
)


# ===================================================================
# PUBLIC MODE DETECTION
# ===================================================================

def is_public_mode() -> bool:
    """Check if accessed via public sharing URL (?mode=view)."""
    return st.query_params.get("mode") in ("view", "public")


def get_public_params() -> dict:
    """Extract school_id and class from URL for public view."""
    return {
        "school_id": st.query_params.get("school_id", ""),
        "class": st.query_params.get("class", ""),
    }


# ===================================================================
# ROLE RESOLUTION
# ===================================================================

def resolve_role(school_id: str, email: str) -> dict:
    """
    Determine the user's role for a specific school.
    Returns: {role: 'director'|'teacher'|'none', allowed_classes: [...]}
    """
    school = get_school(school_id)
    if not school:
        return {"role": "none", "allowed_classes": []}

    # Check if user is the school owner (director)
    if school.get("owner_email", "").lower() == email.lower():
        return {
            "role": "director",
            "allowed_classes": school.get("classes", []),
        }

    # Check permissions sub-collection
    perm = get_user_permission(school_id, email)
    if perm:
        return {
            "role": perm.get("role", "teacher"),
            "allowed_classes": perm.get("allowed_classes", []),
        }

    return {"role": "none", "allowed_classes": []}


# ===================================================================
# MAIN AUTHENTICATION FLOW
# ===================================================================

def authenticate() -> dict:
    """
    Run the full authentication flow.

    Returns a dict:
        {
            "authenticated": bool,
            "is_public": bool,
            "email": str | None,
            "name": str | None,
            "role": "director" | "teacher" | "public" | None,
            "school_id": str | None,
            "school_name": str | None,
            "allowed_classes": list[str],
            "schools": list[dict],   # all schools the user has access to
        }
    """
    result = {
        "authenticated": False,
        "is_public": False,
        "email": None,
        "name": None,
        "role": None,
        "school_id": None,
        "school_name": None,
        "allowed_classes": [],
        "schools": [],
    }

    # ----- PUBLIC MODE -----
    if is_public_mode():
        params = get_public_params()
        school_id = params["school_id"]
        result["is_public"] = True
        result["role"] = "public"
        result["school_id"] = school_id
        result["authenticated"] = True

        if school_id:
            school = get_school(school_id)
            if school:
                result["school_name"] = school.get("name", "")
                result["allowed_classes"] = school.get("classes", [])
                pub_class = params.get("class", "")
                if pub_class and pub_class in result["allowed_classes"]:
                    result["allowed_classes"] = [pub_class]
        return result

    # ----- OIDC AUTH (Google) -----
    oidc_configured = False
    try:
        auth_cfg = st.secrets.get("auth", {})
        client_id = auth_cfg.get("client_id", "")
        # Reject all known placeholders
        placeholders = ("YOUR", "VOTRE", "CHANGE_ME", "TODO", "REPLACE", "xxx", "EXAMPLE")
        is_placeholder = any(p in client_id.upper() for p in (p.upper() for p in placeholders))
        oidc_configured = (
            bool(client_id)
            and client_id.endswith("apps.googleusercontent.com")
            and not is_placeholder
        )
    except Exception:
        pass

    if oidc_configured:
        return _oidc_flow(result)

    # ----- FALLBACK: Simple email form -----
    return _simple_auth_flow(result)


def _oidc_flow(result: dict) -> dict:
    """Handle Google OIDC authentication via Streamlit built-in."""
    if not st.user.is_logged_in:
        st.markdown(
            '<h2 style="text-align:center;color:#1A237E;">לוח מבחנים</h2>'
            '<p style="text-align:center;color:#5C6BC0;">התחבר כדי להמשיך</p>',
            unsafe_allow_html=True,
        )
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.button("התחבר עם Google", on_click=st.login, use_container_width=True, type="primary")
        return result

    email = (st.user.email or "").lower()
    name = st.user.name or email
    result["authenticated"] = True
    result["email"] = email
    result["name"] = name

    # Sidebar user info + logout
    with st.sidebar:
        st.markdown(f"**{name}**")
        st.caption(email)
        st.button("התנתק", on_click=st.logout)

    return _resolve_schools(result, email)


def _simple_auth_flow(result: dict) -> dict:
    """Fallback auth: simple email input (for local dev without Google OAuth)."""
    if "auth_email" not in st.session_state:
        st.markdown(
            '<h2 style="text-align:center;color:#1A237E;">לוח מבחנים</h2>'
            '<p style="text-align:center;color:#5C6BC0;">התחבר כדי להמשיך</p>',
            unsafe_allow_html=True,
        )
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            with st.form("login_form"):
                email = st.text_input("אימייל", placeholder="you@school.co.il")
                password = st.text_input("סיסמה", type="password")
                submitted = st.form_submit_button("התחבר", use_container_width=True, type="primary")
                if submitted and email.strip():
                    st.session_state["auth_email"] = email.strip().lower()
                    st.session_state["auth_name"] = email.strip().split("@")[0]
                    st.rerun()
            st.caption("במצב פיתוח: הזן כל אימייל לכניסה")
        return result

    email = st.session_state["auth_email"]
    name = st.session_state.get("auth_name", email)
    result["authenticated"] = True
    result["email"] = email
    result["name"] = name

    with st.sidebar:
        st.markdown(f"**{name}**")
        st.caption(email)
        if st.button("התנתק"):
            del st.session_state["auth_email"]
            if "auth_name" in st.session_state:
                del st.session_state["auth_name"]
            st.rerun()

    return _resolve_schools(result, email)


def _resolve_schools(result: dict, email: str) -> dict:
    """After authentication, find which schools the user belongs to."""
    schools = list_schools_for_user(email)
    result["schools"] = schools

    if not schools:
        # New user - no schools yet. They'll see the "create school" flow.
        result["role"] = "director"  # Default to director for new users
        return result

    # If user has exactly one school, auto-select it
    if len(schools) == 1:
        school = schools[0]
        result["school_id"] = school["id"]
        result["school_name"] = school.get("name", "")
        result["role"] = school.get("user_role", "teacher")
        if result["role"] == "director":
            result["allowed_classes"] = school.get("classes", [])
        else:
            result["allowed_classes"] = school.get("allowed_classes", [])
        return result

    # Multiple schools - user picks from sidebar
    if "selected_school_id" in st.session_state:
        sid = st.session_state["selected_school_id"]
        for s in schools:
            if s["id"] == sid:
                result["school_id"] = s["id"]
                result["school_name"] = s.get("name", "")
                result["role"] = s.get("user_role", "teacher")
                if result["role"] == "director":
                    result["allowed_classes"] = s.get("classes", [])
                else:
                    result["allowed_classes"] = s.get("allowed_classes", [])
                return result

    # Show school selector in sidebar
    with st.sidebar:
        st.markdown("### בחר מוסד")
        school_options = {s["id"]: f'{s.get("name", s["id"])}' for s in schools}
        selected = st.selectbox(
            "מוסד לימודים",
            options=list(school_options.keys()),
            format_func=lambda x: school_options[x],
            key="school_selector",
        )
        if selected:
            st.session_state["selected_school_id"] = selected
            for s in schools:
                if s["id"] == selected:
                    result["school_id"] = s["id"]
                    result["school_name"] = s.get("name", "")
                    result["role"] = s.get("user_role", "teacher")
                    if result["role"] == "director":
                        result["allowed_classes"] = s.get("classes", [])
                    else:
                        result["allowed_classes"] = s.get("allowed_classes", [])

    return result
