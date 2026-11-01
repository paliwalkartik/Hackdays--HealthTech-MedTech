"""
tests/test_refactored_modules.py — Tests for db, auth, and hospitals modules
"""

import json
import pytest
from auth import decode_session, encode_session
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


def test_auth_session_token_encode_decode():
    """Verify session token HMAC signing, decoding, and tamper rejection."""
    user = {"name": "Test Patient", "email": "patient@hospital.org", "picture": "http://img.test"}
    token = encode_session(user)
    assert isinstance(token, str)
    assert "." in token

    decoded = decode_session(token)
    assert decoded == user

    # Tampered payload must fail verification
    payload, sig = token.rsplit(".", 1)
    tampered_token = f"dGFtcGVyZWQ.{sig}"
    assert decode_session(tampered_token) is None

    # Invalid token structure must return None
    assert decode_session("invalid-no-dot") is None


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

