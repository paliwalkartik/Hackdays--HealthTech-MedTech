"""
auth.py — Authentication, OAuth2 Flow, Session Token, and Cookie Helpers
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any, Dict, Optional

import google_auth_oauthlib.flow
from googleapiclient.discovery import build
import streamlit as st
import streamlit.components.v1 as components

from config import config

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

# ── Config ────────────────────────────────────────────────────────────────────
CREDENTIALS_FILE = "google_credentials.json"
REDIRECT_URI = "http://localhost:8501"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
]
COOKIE_SECRET = os.environ.get("COOKIE_SECRET") or "intelli_vitals_2026_secret_hmac_key"
COOKIE_NAME = "iv_session"


# ── Session Token (cookie-based persistence) ──────────────────────────────────
def _sign(data: str) -> str:
    return hmac.new(COOKIE_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()


def encode_session(user_info: Dict[str, Any]) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(user_info).encode()).decode()
    sig = _sign(payload)
    return f"{payload}.{sig}"


def decode_session(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        return json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
    except Exception:
        return None


def set_cookie(token: str) -> None:
    max_age = 60 * 60 * 24 * config.SESSION_TTL_DAYS
    components.html(
        f"""<script>
    document.cookie = "{COOKIE_NAME}={token}; path=/; max-age={max_age}; SameSite=Lax";
    </script>""",
        height=0,
    )


def clear_cookie() -> None:
    components.html(
        f"""<script>
    document.cookie = "{COOKIE_NAME}=; path=/; max-age=0";
    </script>""",
        height=0,
    )


def get_cookie() -> str:
    cookies = st.context.cookies
    return cookies.get(COOKIE_NAME, "")


# ── OAuth ─────────────────────────────────────────────────────────────────────
def build_flow():
    return google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        autogenerate_code_verifier=False,
    )


def get_auth_url() -> str:
    flow = build_flow()
    url, state = flow.authorization_url(access_type="offline", prompt="select_account")
    st.session_state["oauth_state"] = state
    return url


def exchange_code(code: str) -> Optional[Dict[str, Any]]:
    try:
        flow = build_flow()
        flow.fetch_token(code=code)
        svc = build("oauth2", "v2", credentials=flow.credentials)
        return svc.userinfo().get().execute()
    except Exception as e:
        st.error(f"Login error: {e}")
        return None


def init_session_state() -> None:
    """Restore user session from cookie if present and valid."""
    if "connected" not in st.session_state:
        token = get_cookie()
        if token:
            user = decode_session(token)
            if user:
                st.session_state["connected"] = True
                st.session_state["user_info"] = user
                return
        st.session_state["connected"] = False
        st.session_state["user_info"] = {}


def handle_oauth_callback() -> None:
    """Check query params for OAuth authorization code and log the user in."""
    auth_code = st.query_params.get("code")
    if auth_code and not st.session_state.get("connected"):
        st.query_params.clear()
        user = exchange_code(auth_code)
        if user:
            st.session_state["connected"] = True
            st.session_state["user_info"] = user
            set_cookie(encode_session(user))
            st.rerun()


def logout() -> None:
    """Clear session cookie and reset session state."""
    clear_cookie()
    st.session_state["connected"] = False
    st.session_state["user_info"] = {}
    st.rerun()

