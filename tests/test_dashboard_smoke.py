"""
tests/test_dashboard_smoke.py — Streamlit AppTest Smoke Tests
"""

import pytest
from streamlit.testing.v1 import AppTest


def test_dashboard_renders_login_wall_unauthenticated():
    """Verify that dashboard renders login wall and halts when user is unauthenticated."""
    at = AppTest.from_file("dashboard.py", default_timeout=20)
    at.run()

    # Verify no unhandled exceptions
    assert len(at.exception) == 0, f"AppTest raised unexpected exception: {at.exception}"

    # Verify session state flags user as not connected
    assert at.session_state["connected"] is False
    assert at.session_state["user_info"] == {}

    # Verify key login wall content is rendered in markdown
    all_markdown = " ".join(m.value for m in at.markdown)
    assert "Intelli-Vitals" in all_markdown
    assert "Touchless Health Monitoring" in all_markdown
    assert "Sign in to access your health dashboard" in all_markdown
    assert "rPPG Heart Rate" in all_markdown
    assert "Report Analysis" in all_markdown
    assert "Health History" in all_markdown

    # Tabs and telemetry elements must NOT be rendered when unauthenticated
    assert len(at.tabs) == 0
