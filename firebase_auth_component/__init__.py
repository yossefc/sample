"""Firebase Auth Streamlit Component.

Renders a Firebase Auth login/register/reset-password widget in the browser
and returns the idToken back to Python via Streamlit's component protocol.
"""

import os
import streamlit.components.v1 as components

_COMPONENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

_firebase_auth_component = components.declare_component(
    "firebase_auth",
    path=_COMPONENT_DIR,
)


def firebase_auth_widget(
    api_key: str,
    auth_domain: str,
    project_id: str,
    height: int = 520,
    action: str = "auth",
    key: str = "firebase_auth",
) -> dict | None:
    """Render the Firebase Auth widget.

    Returns a dict with {idToken, email, displayName, uid} on successful auth,
    or None if the user has not yet authenticated.
    """
    return _firebase_auth_component(
        api_key=api_key,
        auth_domain=auth_domain,
        project_id=project_id,
        height=height,
        action=action,
        key=key,
        default=None,
    )
