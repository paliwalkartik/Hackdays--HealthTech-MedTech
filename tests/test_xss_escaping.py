"""
tests/test_xss_escaping.py — XSS escaping unit tests and AppTest integration tests.

Verifies that user/model-controlled strings are escaped before reaching
unsafe_allow_html=True blocks in the Streamlit UI.
"""

from __future__ import annotations

import os
import types
import unittest.mock as mock

import pytest

XSS_PAYLOAD = "<img src=x onerror=alert(1)>"
ESCAPED_PAYLOAD = "&lt;img src=x onerror=alert(1)&gt;"


# ── Unit tests for ui/safe.py ─────────────────────────────────────────────────


def test_esc_basic():
    from ui.safe import esc

    assert esc("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_esc_none_returns_empty():
    from ui.safe import esc

    assert esc(None) == ""


def test_esc_int():
    from ui.safe import esc

    assert esc(42) == "42"


def test_esc_xss_payload():
    from ui.safe import esc

    assert esc(XSS_PAYLOAD) == ESCAPED_PAYLOAD


def test_esc_quotes():
    from ui.safe import esc

    assert esc('"hello"') == "&quot;hello&quot;"
    assert esc("'world'") == "&#x27;world&#x27;"


def test_esc_list_basic():
    from ui.safe import esc_list

    assert esc_list(["<b>bold</b>", "<i>ital</i>"]) == ["&lt;b&gt;bold&lt;/b&gt;", "&lt;i&gt;ital&lt;/i&gt;"]


def test_esc_list_with_none():
    from ui.safe import esc_list

    result = esc_list(["<b>", None])
    assert result == ["&lt;b&gt;", ""]


def test_esc_list_none_input():
    from ui.safe import esc_list

    assert esc_list(None) == []


def test_esc_list_non_iterable():
    from ui.safe import esc_list

    assert esc_list(42) == []


def test_safe_picture_url_https_allowed():
    from ui.safe import safe_picture_url

    url = "https://lh3.googleusercontent.com/a/avatar.jpg"
    assert safe_picture_url(url) == url


def test_safe_picture_url_http_rejected():
    from ui.safe import safe_picture_url

    assert safe_picture_url("http://example.com/pic.jpg") == ""


def test_safe_picture_url_javascript_rejected():
    from ui.safe import safe_picture_url

    assert safe_picture_url("javascript:alert(1)") == ""


def test_safe_picture_url_none():
    from ui.safe import safe_picture_url

    assert safe_picture_url(None) == ""


def test_safe_picture_url_escapes_special_chars():
    from ui.safe import safe_picture_url

    assert safe_picture_url('https://example.com/img?a=1&b=<x>"') == \
        "https://example.com/img?a=1&amp;b=&lt;x&gt;&quot;"


# ── auth.py sanitize_picture_url: https-only ─────────────────────────────────


def test_auth_sanitize_picture_url_https_only():
    from auth import sanitize_picture_url

    assert sanitize_picture_url("https://lh3.googleusercontent.com/photo.jpg")
    assert sanitize_picture_url("http://example.com/photo.jpg") == ""
    assert sanitize_picture_url("javascript:evil()") == ""
    assert sanitize_picture_url("") == ""
    assert sanitize_picture_url(None) == ""  # type: ignore[arg-type]


# ── AppTest: snapshot view escapes XSS payload ────────────────────────────────


@pytest.fixture()
def dev_env(monkeypatch):
    """Set environment variables for dev login mode."""
    monkeypatch.setenv("IV_DEV_LOGIN", "1")
    monkeypatch.setenv("IV_API_TOKEN", "test-token-xss")
    monkeypatch.setenv("IV_DISABLE_POLLING", "1")


def _make_response(status_code: int, json_data: dict):
    """Build a minimal mock requests.Response."""
    resp = mock.MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def test_snapshot_xss_payload_escaped(dev_env, monkeypatch):
    """clinical_status / visual_assessment / recommendation from /consult must be escaped."""
    from streamlit.testing.v1 import AppTest

    consult_payload = {
        "clinical_status": XSS_PAYLOAD,
        "visual_assessment": XSS_PAYLOAD,
        "recommendation": XSS_PAYLOAD,
        "average_bpm": 72,
    }
    vitals_payload = {
        "bpm": 72,
        "pulse": 0.5,
        "is_stable": True,
        "is_completed": False,
        "stable_duration": 30.0,
    }

    def mock_get(url, **kwargs):
        if "/consult" in url:
            return _make_response(200, consult_payload)
        if "/vitals" in url:
            return _make_response(200, vitals_payload)
        return _make_response(404, {})

    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr("requests.post", lambda *a, **kw: _make_response(200, {}))

    at = AppTest.from_file("dashboard.py", default_timeout=30)
    at.run()

    # Dev login
    if at.button:
        dev_login_btns = [b for b in at.button if "Dev Mode" in (b.label or "")]
        if dev_login_btns:
            dev_login_btns[0].click().run()

    # Click the snapshot button
    snapshot_btns = [b for b in at.button if b.key == "snapshot_btn"]
    if snapshot_btns:
        snapshot_btns[0].click().run()

    # Collect all rendered markdown content
    all_markdown = " ".join(
        str(m.value) for m in at.markdown if m.value
    )

    # Raw XSS payload must NOT appear verbatim
    assert XSS_PAYLOAD not in all_markdown, (
        f"Raw XSS payload found unescaped in snapshot markdown: {XSS_PAYLOAD!r}"
    )
    # Escaped form must appear (confirms value was rendered, just safely)
    assert ESCAPED_PAYLOAD in all_markdown or "&lt;img" in all_markdown, (
        "Expected escaped payload not found — was the snapshot block rendered?"
    )


def test_report_analysis_xss_payload_escaped(dev_env, monkeypatch):
    """Report analysis fields from /analyze_report must be escaped in the UI."""
    from streamlit.testing.v1 import AppTest

    analysis_payload = {
        "summary": XSS_PAYLOAD,
        "urgency_level": "Routine",
        "medical_specialty": XSS_PAYLOAD,
        "health_risks": [XSS_PAYLOAD],
        "lifestyle_measures": [XSS_PAYLOAD],
        "action_plan": XSS_PAYLOAD,
        "visual_observations": XSS_PAYLOAD,
    }

    vitals_payload = {
        "bpm": 72,
        "pulse": 0.5,
        "is_stable": False,
        "is_completed": False,
        "stable_duration": 0.0,
    }

    def mock_get(url, **kwargs):
        if "/vitals" in url:
            return _make_response(200, vitals_payload)
        return _make_response(404, {})

    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr("requests.post", lambda *a, **kw: _make_response(200, analysis_payload))

    at = AppTest.from_file("dashboard.py", default_timeout=30)
    at.run()

    # Dev login
    if at.button:
        dev_login_btns = [b for b in at.button if "Dev Mode" in (b.label or "")]
        if dev_login_btns:
            dev_login_btns[0].click().run()

    # Inject last_analysis directly into session state to trigger the hospital/report block
    at.session_state["last_analysis"] = analysis_payload
    at.run()

    all_markdown = " ".join(str(m.value) for m in at.markdown if m.value)

    # Raw XSS payload must NOT appear verbatim in any markdown
    assert XSS_PAYLOAD not in all_markdown, (
        f"Raw XSS payload found unescaped in report analysis markdown: {XSS_PAYLOAD!r}"
    )

