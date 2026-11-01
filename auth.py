"""
auth.py — Streamlit OIDC Authentication, User Profile Sanitization, and Dev Mode Bypass
"""

from __future__ import annotations

import html
import os
from typing import Any, Dict, Optional

import streamlit as st


# ── Dev Mode User ─────────────────────────────────────────────────────────────
DEV_USER: Dict[str, Any] = {
    "sub": "dev-user-001",
    "email": "dev@intellivitals.local",
    "name": "Dev User",
    "picture": "",
    "is_logged_in": True,
}


def is_dev_mode() -> bool:
    """Check whether local development login bypass is enabled via environment."""
    return os.environ.get("IV_DEV_LOGIN") == "1"


def is_auth_configured() -> bool:
    """Check whether Streamlit OIDC auth is configured in secrets.toml or st.secrets."""
    try:
        # Check local .streamlit/secrets.toml first
        project_secrets = os.path.join(os.getcwd(), ".streamlit", "secrets.toml")
        if os.path.isfile(project_secrets):
            try:
                import toml

                with open(project_secrets, "r", encoding="utf-8") as f:
                    data = toml.load(f)
                auth_data = data.get("auth", {})
                google_data = (
                    auth_data.get("google", {})
                    if isinstance(auth_data.get("google"), dict)
                    else {}
                )
                has_client_id = bool(auth_data.get("client_id") or google_data.get("client_id"))
                has_client_secret = bool(auth_data.get("client_secret") or google_data.get("client_secret"))
                has_cookie_secret = bool(auth_data.get("cookie_secret"))
                return has_client_id and has_client_secret and has_cookie_secret
            except Exception:
                pass

        # Check st.secrets fallback
        try:
            if "auth" in st.secrets:
                auth_data = st.secrets["auth"]
                google_data = (
                    auth_data.get("google", {})
                    if isinstance(auth_data.get("google"), dict)
                    else {}
                )
                has_client_id = bool(auth_data.get("client_id") or google_data.get("client_id"))
                has_client_secret = bool(auth_data.get("client_secret") or google_data.get("client_secret"))
                has_cookie_secret = bool(auth_data.get("cookie_secret"))
                return has_client_id and has_client_secret and has_cookie_secret
        except Exception:
            pass

        return False
    except Exception:
        return False


def is_logged_in() -> bool:
    """Return True if user is authenticated via Streamlit OIDC or dev bypass."""
    # Check Dev Mode bypass session
    if is_dev_mode() and st.session_state.get("dev_user_logged_in", False):
        user = st.session_state.get("dev_user", DEV_USER)
        st.session_state["connected"] = True
        st.session_state["user_info"] = user
        return True

    # Check Streamlit built-in OIDC user
    try:
        if st.user.get("is_logged_in", False):
            user_data = {
                "sub": str(st.user.get("sub", "")),
                "email": str(st.user.get("email", "")),
                "name": str(st.user.get("name", "User")),
                "picture": str(st.user.get("picture", "")),
                "is_logged_in": True,
            }
            st.session_state["connected"] = True
            st.session_state["user_info"] = user_data
            return True
    except Exception:
        pass

    st.session_state["connected"] = False
    st.session_state["user_info"] = {}
    return False


def get_current_user() -> Optional[Dict[str, Any]]:
    """Return current user dict with sub, email, name, picture, or None."""
    if is_dev_mode() and st.session_state.get("dev_user_logged_in", False):
        return st.session_state.get("dev_user", DEV_USER)

    try:
        if st.user.get("is_logged_in", False):
            return {
                "sub": str(st.user.get("sub", "")),
                "email": str(st.user.get("email", "")),
                "name": str(st.user.get("name", "User")),
                "picture": str(st.user.get("picture", "")),
                "is_logged_in": True,
            }
    except Exception:
        pass
    return None


def sanitize_picture_url(url: str) -> str:
    """Sanitize and validate picture URL, ensuring only https:// scheme and html escaping.

    http:// is rejected — Google profile photos are always https; accepting http
    would allow downgrade attacks via a mixed-content avatar URL.
    """
    if not url or not isinstance(url, str):
        return ""
    clean_url = url.strip()
    if clean_url.startswith("https://"):
        return html.escape(clean_url, quote=True)
    return ""


def get_safe_user_profile(user: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Return an HTML-escaped, sanitized user profile dictionary."""
    if user is None:
        user = get_current_user() or {}
    raw_name = str(user.get("name") or "User")
    raw_email = str(user.get("email") or "")
    raw_sub = str(user.get("sub") or "")
    raw_pic = str(user.get("picture") or "")

    name = html.escape(raw_name)
    email = html.escape(raw_email)
    sub = html.escape(raw_sub)
    picture = sanitize_picture_url(raw_pic)
    first_name = html.escape(raw_name.split()[0] if raw_name else "User")

    return {
        "name": name,
        "email": email,
        "sub": sub,
        "picture": picture,
        "first_name": first_name,
    }


def login() -> None:
    """Initiate Google login via Streamlit OIDC."""
    try:
        st.login("google")
    except Exception:
        try:
            st.login()
        except Exception as e:
            st.error(f"Login failed to initiate: {e}")


def dev_login() -> None:
    """Log in using local dev mode mock user."""
    st.session_state["dev_user_logged_in"] = True
    st.session_state["dev_user"] = DEV_USER
    st.session_state["connected"] = True
    st.session_state["user_info"] = DEV_USER


def logout() -> None:
    """Log out current user, clear session state, and invoke st.logout."""
    st.session_state["dev_user_logged_in"] = False
    st.session_state.pop("dev_user", None)
    st.session_state["connected"] = False
    st.session_state["user_info"] = {}
    try:
        st.logout()
    except Exception:
        pass
    st.rerun()
