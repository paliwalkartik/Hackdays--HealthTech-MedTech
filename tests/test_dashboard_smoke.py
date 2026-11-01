"""
tests/test_dashboard_smoke.py — Streamlit AppTest Smoke Tests
"""

import pytest
from streamlit.testing.v1 import AppTest


def test_dashboard_renders_setup_screen_unauthenticated(monkeypatch):
    """Verify that dashboard renders setup screen and halts when unauthenticated without secrets."""
    monkeypatch.delenv("IV_DEV_LOGIN", raising=False)
    at = AppTest.from_file("dashboard.py", default_timeout=20)
    at.run()

    # Verify no unhandled exceptions
    assert len(at.exception) == 0, f"AppTest raised unexpected exception: {at.exception}"

    # Verify session state flags user as not connected
    assert at.session_state["connected"] is False
    assert at.session_state["user_info"] == {}

    # Verify key login wall / setup guide content is rendered in markdown
    all_markdown = " ".join(m.value for m in at.markdown)
    assert "Intelli-Vitals" in all_markdown
    assert "Touchless Health Monitoring" in all_markdown
    assert "Authentication Setup Required" in all_markdown
    assert "rPPG Heart Rate" in all_markdown
    assert "Report Analysis" in all_markdown
    assert "Health History" in all_markdown

    # Tabs and telemetry elements must NOT be rendered when unauthenticated
    assert len(at.tabs) == 0


def test_dashboard_renders_dev_mode_banner_unauthenticated(monkeypatch):
    """Verify that dashboard renders DEV MODE banner and bypass login button when IV_DEV_LOGIN=1."""
    monkeypatch.setenv("IV_DEV_LOGIN", "1")
    at = AppTest.from_file("dashboard.py", default_timeout=20)
    at.run()

    assert len(at.exception) == 0, f"AppTest raised unexpected exception: {at.exception}"
    assert at.session_state["connected"] is False

    all_markdown = " ".join(m.value for m in at.markdown)
    assert "DEV MODE ACTIVE" in all_markdown

    # Dev login button should be present in button list
    button_labels = [b.label for b in at.button]
    assert any("Dev Login" in label for label in button_labels)

    # Tabs still not rendered before clicking dev login
    assert len(at.tabs) == 0


def test_dashboard_dev_mode_login_flow(monkeypatch):
    """Verify that clicking dev mode bypass button authenticates user and unlocks dashboard tabs."""
    monkeypatch.setenv("IV_DEV_LOGIN", "1")
    monkeypatch.setenv("IV_DISABLE_POLLING", "1")
    at = AppTest.from_file("dashboard.py", default_timeout=20)
    at.run()

    # Click the wall dev login button
    dev_button = next(b for b in at.button if "Dev" in b.label)
    dev_button.click().run()

    assert len(at.exception) == 0, f"AppTest raised unexpected exception: {at.exception}"
    assert at.session_state["connected"] is True
    assert at.session_state["user_info"]["email"] == "dev@intellivitals.local"

    # Dashboard tabs should now be rendered
    assert len(at.tabs) == 3
    tab_labels = [t.label for t in at.tabs]
    assert any("Live Monitoring" in l for l in tab_labels)
    assert any("Past Records" in l for l in tab_labels)
    assert any("Report Analysis" in l for l in tab_labels)
