"""
tests/test_refactored_modules.py — Tests for db, auth, and hospitals modules
"""

import json
import pytest
import streamlit as st
from auth import (
    DEV_USER,
    dev_login,
    get_current_user,
    get_safe_user_profile,
    is_auth_configured,
    is_dev_mode,
    is_logged_in,
    logout,
    sanitize_picture_url,
)
from db import fetch_logs, init_db, save_log
from hospitals import HOSPITAL_DB, DEFAULT_HOSPITALS, get_hospitals_for_specialty


def test_db_context_managed_operations(tmp_path):
    """Verify init_db, save_log, and fetch_logs with context-managed connection."""
    db_file = str(tmp_path / "test_records.db")

    init_db(db_path=db_file)
    assert fetch_logs("user@test.com", db_path=db_file) == []

    analysis_payload = json.dumps({"clinical_status": "Normal", "recommendation": "Rest"})
    save_log("user@test.com", 72.5, analysis_payload, db_path=db_file)

    logs = fetch_logs("user@test.com", db_path=db_file)
    assert len(logs) == 1
    timestamp, bpm, stored_analysis = logs[0]
    assert bpm == 72.5
    assert json.loads(stored_analysis)["clinical_status"] == "Normal"

    # Verify filtering by user
    assert fetch_logs("other@test.com", db_path=db_file) == []


def test_auth_dev_mode_and_bypass(monkeypatch):
    """Verify dev mode detection, dev login state mutation, and logout."""
    # Ensure dev mode is disabled initially
    monkeypatch.delenv("IV_DEV_LOGIN", raising=False)
    assert is_dev_mode() is False
    assert is_logged_in() is False

    # Enable dev mode via environment
    monkeypatch.setenv("IV_DEV_LOGIN", "1")
    assert is_dev_mode() is True

    # Dev login sets state and flags user as logged in
    dev_login()
    assert is_logged_in() is True
    user = get_current_user()
    assert user is not None
    assert user["sub"] == DEV_USER["sub"]
    assert user["email"] == DEV_USER["email"]

    # Logout resets state
    # Mock st.rerun to prevent Streamlit rerun exception in bare test
    monkeypatch.setattr(st, "rerun", lambda: None)
    logout()
    assert is_logged_in() is False
    assert get_current_user() is None


def test_auth_safe_user_profile_escaping():
    """Verify HTML escaping for name, email, sub, and URL sanitization for picture."""
    # Malicious inputs
    malicious_user = {
        "name": "Jane <script>alert('xss')</script> Doe",
        "email": 'user"onerror="alert(1)@example.com',
        "sub": '<img src=x onerror=alert("sub")>',
        "picture": "javascript:alert('malicious')",
    }

    profile = get_safe_user_profile(malicious_user)

    # Assert dangerous characters are HTML-escaped
    assert "<script>" not in profile["name"]
    assert "&lt;script&gt;" in profile["name"]
    assert "<img" not in profile["sub"]
    assert "&lt;img" in profile["sub"]
    assert 'user"onerror' not in profile["email"]
    assert "user&quot;onerror" in profile["email"]

    # JavaScript protocol URL must be rejected and cleared
    assert profile["picture"] == ""

    # Safe picture URL must be preserved
    safe_user = {
        "name": "Alice Smith",
        "email": "alice@hospital.org",
        "sub": "sub-12345",
        "picture": "https://lh3.googleusercontent.com/avatar.jpg",
    }
    safe_profile = get_safe_user_profile(safe_user)
    assert safe_profile["picture"] == "https://lh3.googleusercontent.com/avatar.jpg"
    assert safe_profile["first_name"] == "Alice"


def test_auth_is_auth_configured(tmp_path, monkeypatch):
    """Verify is_auth_configured accurately detects secrets.toml configuration."""
    # When no secrets.toml exists in cwd
    monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))
    assert is_auth_configured() is False

    # Create dummy .streamlit/secrets.toml with complete [auth]
    secrets_dir = tmp_path / ".streamlit"
    secrets_dir.mkdir(parents=True)
    secrets_file = secrets_dir / "secrets.toml"
    secrets_file.write_text(
        """
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "test-secret-at-least-32-chars-long-12345"
client_id = "test-client-id"
client_secret = "test-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
""",
        encoding="utf-8",
    )
    assert is_auth_configured() is True


def test_hospitals_data_and_lookup():
    """Verify hospitals loader and specialty lookup."""
    assert len(HOSPITAL_DB) >= 5
    assert "Cardiology" in HOSPITAL_DB
    assert "Neurology" in HOSPITAL_DB

    cardio_hospitals = get_hospitals_for_specialty("Cardiology")
    assert len(cardio_hospitals) >= 3
    assert any("Bansal Hospital" in h["name"] for h in cardio_hospitals)

    # Fallback to default hospitals when unknown specialty
    unknown = get_hospitals_for_specialty("UnknownSpecialtyXYZ")
    assert unknown == DEFAULT_HOSPITALS
