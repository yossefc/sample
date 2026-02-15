"""
auth_manager.py - Firebase Authentication for the school platform.

Uses Firebase Auth REST API (email/password) - no Google Cloud OAuth needed.
Requires `web_api_key` in Streamlit secrets under [firebase].
"""

from urllib.parse import urlsplit

import requests
import streamlit as st

from db_manager import (
    get_school,
    get_user_permission,
    list_schools_for_user,
)


# ───────────────────────────────────────────────
# Public mode helpers
# ───────────────────────────────────────────────

def is_public_mode() -> bool:
    """Check if app is opened in public read-only mode."""
    return st.query_params.get("mode") in ("view", "public")


def get_public_params() -> dict:
    """Extract school_id and class from URL."""
    return {
        "school_id": st.query_params.get("school_id", ""),
        "class": st.query_params.get("class", ""),
    }


# ───────────────────────────────────────────────
# Role resolution
# ───────────────────────────────────────────────

def resolve_role(school_id: str, email: str) -> dict:
    """
    Determine role for a specific school.
    Returns: {role: 'director'|'teacher'|'none', allowed_classes: [...]}.
    """
    school = get_school(school_id)
    if not school:
        return {"role": "none", "allowed_classes": []}

    if school.get("owner_email", "").lower() == email.lower():
        return {
            "role": "director",
            "allowed_classes": school.get("classes", []),
        }

    perm = get_user_permission(school_id, email)
    if perm:
        return {
            "role": perm.get("role", "teacher"),
            "allowed_classes": perm.get("allowed_classes", []),
        }

    return {"role": "none", "allowed_classes": []}


# ───────────────────────────────────────────────
# Firebase Auth REST API
# ───────────────────────────────────────────────

def _get_web_api_key() -> str:
    """Retrieve Firebase Web API Key from secrets."""
    key = st.secrets.get("firebase", {}).get("web_api_key", "")
    if not key:
        key = st.secrets.get("auth", {}).get("web_api_key", "")
    return str(key).strip()


def _build_origin_headers() -> dict:
    """Build Origin/Referer headers for API key referrer restrictions."""
    headers = {"Content-Type": "application/json"}
    try:
        redirect_uri = st.secrets.get("auth", {}).get("redirect_uri", "")
        if redirect_uri:
            parts = urlsplit(str(redirect_uri))
            if parts.scheme and parts.netloc:
                origin = f"{parts.scheme}://{parts.netloc}"
                headers["Origin"] = origin
                headers["Referer"] = f"{origin}/"
        elif hasattr(st, "context") and hasattr(st.context, "headers"):
            host = st.context.headers.get("Host", "")
            scheme = st.context.headers.get("X-Forwarded-Proto", "https")
            if host:
                origin = f"{scheme}://{host}"
                headers["Origin"] = origin
                headers["Referer"] = f"{origin}/"
    except Exception:
        pass
    return headers


def _firebase_sign_in(email: str, password: str) -> dict:
    """Authenticate with Firebase REST API using email/password."""
    api_key = _get_web_api_key()
    if not api_key:
        return {"error": "חסר Firebase Web API Key בקובץ secrets.toml"}

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    headers = _build_origin_headers()

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        data = resp.json()
        if "error" in data:
            err = data.get("error", {}) if isinstance(data.get("error"), dict) else {}
            return {
                "error": err.get("message", str(data.get("error"))),
                "error_code": err.get("status", ""),
            }
        return data
    except Exception as ex:
        return {"error": str(ex)}


def _firebase_sign_up(email: str, password: str) -> dict:
    """Create a new user with Firebase REST API."""
    api_key = _get_web_api_key()
    if not api_key:
        return {"error": "חסר Firebase Web API Key בקובץ secrets.toml"}

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    headers = _build_origin_headers()

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        data = resp.json()
        if "error" in data:
            err = data.get("error", {}) if isinstance(data.get("error"), dict) else {}
            return {
                "error": err.get("message", str(data.get("error"))),
                "error_code": err.get("status", ""),
            }
        return data
    except Exception as ex:
        return {"error": str(ex)}


def _firebase_reset_password(email: str) -> dict:
    """Send password reset email via Firebase REST API."""
    api_key = _get_web_api_key()
    if not api_key:
        return {"error": "חסר Firebase Web API Key בקובץ secrets.toml"}

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
    payload = {"requestType": "PASSWORD_RESET", "email": email}
    headers = _build_origin_headers()

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        data = resp.json()
        if "error" in data:
            err = data.get("error", {}) if isinstance(data.get("error"), dict) else {}
            return {
                "error": err.get("message", str(data.get("error"))),
            }
        return {"success": True}
    except Exception as ex:
        return {"error": str(ex)}


# ───────────────────────────────────────────────
# Login UI
# ───────────────────────────────────────────────

_LOGIN_CSS = """
<style>
.login-container {
    max-width: 400px; margin: 40px auto; padding: 0 20px;
    direction: rtl; font-family: 'Heebo', sans-serif;
}
.login-header {
    text-align: center; margin-bottom: 32px;
}
.login-header h1 {
    color: #1A237E; font-weight: 900; font-size: 2rem;
    margin: 0 0 4px; line-height: 1.2;
}
.login-header p {
    color: #7986CB; font-size: 1rem; margin: 0;
    font-weight: 400;
}
.login-divider {
    display: flex; align-items: center; gap: 12px;
    margin: 18px 0; color: #B0BEC5; font-size: 0.82rem;
}
.login-divider::before, .login-divider::after {
    content: ''; flex: 1; height: 1px; background: #E0E0E0;
}
</style>
"""


def _render_login_ui():
    """Show Firebase email/password login page."""
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    st.markdown(
        '<div class="login-container">'
        '<div class="login-header">'
        '<h1>לוח מבחנים</h1>'
        '<p>התחבר כדי להמשיך</p>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    # Tab: Login or Register
    if "login_tab" not in st.session_state:
        st.session_state["login_tab"] = "login"

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_register = st.tabs(["כניסה", "הרשמה"])

        with tab_login:
            with st.form("login_form", clear_on_submit=False):
                email = st.text_input("אימייל", placeholder="you@school.co.il", key="login_email")
                password = st.text_input("סיסמה", type="password", key="login_pass")
                submitted = st.form_submit_button("התחבר", use_container_width=True, type="primary")

                if submitted:
                    _handle_login(email, password)

            # Forgot password
            if st.button("שכחתי סיסמה", key="forgot_pass_btn"):
                st.session_state["show_reset"] = True

            if st.session_state.get("show_reset"):
                reset_email = st.text_input("אימייל לאיפוס", key="reset_email_input", placeholder="you@school.co.il")
                if st.button("שלח קישור איפוס", key="send_reset_btn"):
                    if reset_email and reset_email.strip():
                        result = _firebase_reset_password(reset_email.strip())
                        if "error" in result:
                            st.error(f"שגיאה: {result['error']}")
                        else:
                            st.success("נשלח קישור לאיפוס סיסמה לאימייל שלך")
                            st.session_state["show_reset"] = False
                    else:
                        st.warning("הזן אימייל")

        with tab_register:
            with st.form("register_form", clear_on_submit=False):
                reg_email = st.text_input("אימייל", placeholder="you@school.co.il", key="reg_email")
                reg_pass = st.text_input("סיסמה", type="password", key="reg_pass")
                reg_pass2 = st.text_input("אימות סיסמה", type="password", key="reg_pass2")
                reg_submitted = st.form_submit_button("הרשמה", use_container_width=True, type="primary")

                if reg_submitted:
                    _handle_register(reg_email, reg_pass, reg_pass2)


def _handle_login(email: str, password: str):
    """Process login form submission."""
    if not _get_web_api_key():
        st.error("חסרה הגדרת Firebase Web API Key בקובץ secrets.toml")
        return
    if not email or not email.strip():
        st.warning("אנא הזן אימייל")
        return
    if not password:
        st.warning("אנא הזן סיסמה")
        return

    resp = _firebase_sign_in(email.strip(), password)
    if "error" in resp:
        _show_firebase_error(resp)
    else:
        st.session_state["auth_email"] = resp["email"].lower()
        st.session_state["auth_name"] = resp.get("displayName") or resp["email"].split("@")[0]
        st.session_state["auth_token"] = resp["idToken"]
        st.rerun()


def _handle_register(email: str, password: str, password2: str):
    """Process registration form submission."""
    if not _get_web_api_key():
        st.error("חסרה הגדרת Firebase Web API Key בקובץ secrets.toml")
        return
    if not email or not email.strip():
        st.warning("אנא הזן אימייל")
        return
    if not password or len(password) < 6:
        st.warning("הסיסמה חייבת להכיל לפחות 6 תווים")
        return
    if password != password2:
        st.warning("הסיסמאות אינן תואמות")
        return

    resp = _firebase_sign_up(email.strip(), password)
    if "error" in resp:
        err_msg = resp.get("error", "")
        if "EMAIL_EXISTS" in err_msg:
            st.error("אימייל זה כבר רשום. נסה להתחבר.")
        elif "WEAK_PASSWORD" in err_msg:
            st.error("הסיסמה חלשה מדי. נסה סיסמה חזקה יותר.")
        else:
            st.error(f"שגיאה: {err_msg}")
    else:
        st.session_state["auth_email"] = resp["email"].lower()
        st.session_state["auth_name"] = resp.get("displayName") or resp["email"].split("@")[0]
        st.session_state["auth_token"] = resp["idToken"]
        st.success("נרשמת בהצלחה!")
        st.rerun()


def _show_firebase_error(resp: dict):
    """Display a user-friendly Firebase error message."""
    err_msg = resp.get("error", "")
    err_code = str(resp.get("error_code", ""))

    if any(k in err_msg for k in ("INVALID_PASSWORD", "EMAIL_NOT_FOUND", "INVALID_LOGIN_CREDENTIALS")):
        st.error("אימייל או סיסמה שגויים")
    elif "PASSWORD_LOGIN_DISABLED" in err_msg or "OPERATION_NOT_ALLOWED" in err_msg:
        st.error("התחברות באימייל/סיסמה כבויה ב-Firebase.")
        st.caption("ב-Firebase Console: Authentication > Sign-in method > Email/Password > Enable")
    elif "TOO_MANY_ATTEMPTS_TRY_LATER" in err_msg:
        st.error("נחסמת זמנית עקב יותר מדי ניסיונות. נסה שוב מאוחר יותר.")
    elif "Requests from referer" in err_msg or err_code == "API_KEY_HTTP_REFERRER_BLOCKED":
        st.error("הגישה נחסמה בגלל הגדרת API Key.")
        st.caption("עדכן את הגבלות ה-API Key ב-Firebase Console כך שהדומיין מאושר.")
    else:
        st.error(f"שגיאה: {err_msg}")


# ───────────────────────────────────────────────
# Main authenticate function
# ───────────────────────────────────────────────

def authenticate() -> dict:
    """Run authentication and school resolution."""
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

    # Public read-only mode
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

    # Session-authenticated user (Firebase email/password)
    if "auth_email" in st.session_state:
        email = st.session_state["auth_email"]
        name = st.session_state.get("auth_name", email)
        result["authenticated"] = True
        result["email"] = email
        result["name"] = name
        return _resolve_schools(result, email)

    # Not logged in - show login UI
    _render_login_ui()
    return result


# ───────────────────────────────────────────────
# School resolution
# ───────────────────────────────────────────────

def _resolve_schools(result: dict, email: str) -> dict:
    """After authentication, find schools where the user has access."""
    if result is None:
        result = {}

    schools = list_schools_for_user(email)
    if schools is None:
        schools = []

    result["schools"] = schools

    if not schools:
        result["role"] = "director"
        return result

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

    # Multiple schools - let user pick
    if "selected_school_id" in st.session_state:
        sid = st.session_state["selected_school_id"]
        for school in schools:
            if school["id"] == sid:
                result["school_id"] = school["id"]
                result["school_name"] = school.get("name", "")
                result["role"] = school.get("user_role", "teacher")
                if result["role"] == "director":
                    result["allowed_classes"] = school.get("classes", [])
                else:
                    result["allowed_classes"] = school.get("allowed_classes", [])
                return result

    # Show school selector inline (not sidebar)
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
        for school in schools:
            if school["id"] == selected:
                result["school_id"] = school["id"]
                result["school_name"] = school.get("name", "")
                result["role"] = school.get("user_role", "teacher")
                if result["role"] == "director":
                    result["allowed_classes"] = school.get("classes", [])
                else:
                    result["allowed_classes"] = school.get("allowed_classes", [])

    return result
