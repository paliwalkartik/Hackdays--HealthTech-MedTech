"""
tests/test_report_sanitization.py — Tests for untrusted report input sanitization (SEC-3).

Verifies:
- Report text containing <script> is escaped for UI rendering
- javascript: and dangerous pseudo-protocols in URLs are rejected
- Very long strings are capped (e.g. 200 chars per cell, 500 rows)
- RTL and zero-width characters are stripped from report text
- Control characters (ASCII 0x00-0x1F, DEL, C1) are stripped
- Untrusted text cannot forge file paths or break out of HTML attributes
- Only structured, validated findings are saved to the database unless
  the user chooses 'save original text'
- Parameterized SQL prevents SQL injection from untrusted report findings
"""

from __future__ import annotations

import json
import sqlite3
import pytest

from db import fetch_report_findings, get_connection, init_db, save_report_findings
from ui.safe import (
    DEFAULT_MAX_CELL_CHARS,
    DEFAULT_MAX_ROWS,
    cap_length,
    cap_rows,
    esc,
    safe_cell,
    safe_filename_component,
    safe_html_attr,
    safe_table_rows,
    safe_url,
    sanitize_report_findings,
    sanitize_untrusted_text,
    strip_control_chars,
)


# ---------------------------------------------------------------------------
# 1. <script> XSS and HTML Escaping Tests
# ---------------------------------------------------------------------------


def test_script_tags_escaped_in_cell():
    payload = "<script>alert('xss')</script>"
    rendered = safe_cell(payload)
    assert "<script>" not in rendered
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in rendered


def test_img_onerror_escaped_in_cell():
    payload = '<img src=x onerror="alert(1)">'
    rendered = safe_cell(payload)
    assert "<img" not in rendered
    assert "&lt;img" in rendered
    assert "&quot;" in rendered


def test_script_escaped_in_table_rows():
    rows = [
        {"test": "<script>evil()</script>", "value": "120", "unit": "mg/dL"},
        {"test": "Hemoglobin", "value": "14.2", "unit": "<b onmouseover=alert(1)>g/dL</b>"},
    ]
    cleaned = safe_table_rows(rows)
    assert len(cleaned) == 2
    assert "<script>" not in cleaned[0]["test"]
    assert "&lt;script&gt;" in cleaned[0]["test"]
    assert "<b onmouseover" not in cleaned[1]["unit"]
    assert "&lt;b" in cleaned[1]["unit"]


# ---------------------------------------------------------------------------
# 2. javascript: and Dangerous URL Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        "javascript:alert(document.cookie)",
        "JAVASCRIPT:alert(1)",
        "javascript://%0aalert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
        "relative/path/to/script",
    ],
)
def test_dangerous_urls_rejected(bad_url):
    assert safe_url(bad_url) == ""


def test_safe_urls_accepted_and_escaped():
    good_url = "https://hospital.example.com/portal?id=123&dept=cardio"
    result = safe_url(good_url)
    assert result.startswith("https://")
    assert "&amp;" in result  # HTML-escaped &


def test_url_with_zero_width_or_control_chars_sanitized():
    # Attempting to obfuscate javascript with zero-width spaces or null bytes
    obfuscated = "java\u200Bscript:alert(1)"
    assert safe_url(obfuscated) == ""


# ---------------------------------------------------------------------------
# 3. Length Capping Tests
# ---------------------------------------------------------------------------


def test_cell_length_capped_at_200():
    long_string = "A" * 5000
    capped = cap_length(long_string, max_len=200)
    assert len(capped) == 200

    safe = safe_cell(long_string, max_len=200)
    assert len(safe) == 200


def test_custom_cell_length_cap():
    text = "Short text for unit"
    assert len(safe_cell(text, max_len=10)) == 10


def test_rows_capped_at_500():
    many_rows = [{"test": f"Test {i}", "value": "10"} for i in range(1200)]
    capped = cap_rows(many_rows, max_rows=500)
    assert len(capped) == 500


def test_safe_table_rows_capped():
    many_rows = [{"test": f"Test {i}"} for i in range(800)]
    cleaned = safe_table_rows(many_rows, max_rows=500)
    assert len(cleaned) == 500


# ---------------------------------------------------------------------------
# 4. RTL and Zero-Width Character Stripping Tests
# ---------------------------------------------------------------------------


def test_zero_width_characters_stripped():
    # \u200B (ZWSP), \u200C (ZWNJ), \u200D (ZWJ), \uFEFF (BOM), \u2060 (WJ)
    text_with_zw = "Hemo\u200Bglo\u200Cbin\u200D \uFEFFTest\u2060"
    cleaned = strip_control_chars(text_with_zw)
    assert cleaned == "Hemoglobin Test"
    assert "\u200B" not in cleaned
    assert "\uFEFF" not in cleaned


def test_rtl_override_and_embedding_controls_stripped():
    # \u202E (RLO), \u202D (LRO), \u200F (RLM), \u200E (LRM), \u202A (LRE)
    # Attackers use RLO to disguise malicious extensions (e.g. test\u202Efdp.exe -> testexe.pdf)
    spoofed = "report\u202Efdp.exe"
    cleaned = strip_control_chars(spoofed)
    assert cleaned == "reportfdp.exe"
    assert "\u202E" not in cleaned


def test_zero_width_in_sanitize_report_findings():
    findings = {
        "summary": "Patient has \u200Bnormal vitals\u202E.",
        "health_risks": ["Risk\uFEFF 1", "Risk \u200D2"],
        "medical_specialty": "Cardiology\u200C",
    }
    sanitized = sanitize_report_findings(findings)
    assert "\u200B" not in sanitized["summary"]
    assert "\u202E" not in sanitized["summary"]
    assert "\uFEFF" not in sanitized["health_risks"][0]
    assert "\u200C" not in sanitized["medical_specialty"]


# ---------------------------------------------------------------------------
# 5. ASCII and C1 Control Character Stripping Tests
# ---------------------------------------------------------------------------


def test_ascii_control_characters_stripped():
    # \x00 (NUL), \x07 (BEL), \x08 (BS), \x1B (ESC), \x7F (DEL)
    malicious = "CBC\x00_Report\x07\x08\x1B\x7F"
    cleaned = strip_control_chars(malicious)
    assert cleaned == "CBC_Report"


def test_c1_control_characters_stripped():
    # C1 range \x80-\x9F
    text = "Lab\x80\x9FResults"
    cleaned = strip_control_chars(text)
    assert cleaned == "LabResults"


# ---------------------------------------------------------------------------
# 6. File Path Traversal and HTML Attribute Protection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "untrusted_name, expected_safe",
    [
        ("../../../../etc/passwd", "etc_passwd"),
        ("..\\..\\windows\\system32\\calc.exe", "windows_system32_calc.exe"),
        ("report\x00.pdf", "report.pdf"),
        ("normal_report.pdf", "normal_report.pdf"),
        ("../../../secret", "secret"),
        ("   ", "report_file"),
    ],
)
def test_safe_filename_component(untrusted_name, expected_safe):
    safe_name = safe_filename_component(untrusted_name)
    assert "/" not in safe_name
    assert "\\" not in safe_name
    assert ".." not in safe_name
    assert "\x00" not in safe_name
    assert safe_name == expected_safe


def test_safe_html_attr_escapes_quotes():
    untrusted = 'val" onfocus="alert(1)'
    attr = safe_html_attr(untrusted)
    assert '"' not in attr
    assert "&quot;" in attr


# ---------------------------------------------------------------------------
# 7. Database Storage: Structured Findings vs Raw OCR Text
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_db(tmp_path):
    db_file = str(tmp_path / "test_health.db")
    init_db(db_file)
    return db_file


def test_db_stores_only_structured_findings_by_default(test_db):
    """Raw OCR text must NOT be stored in the DB by default."""
    findings = {
        "summary": "Routine checkup normal",
        "urgency_level": "Routine",
        "health_risks": ["Mild dehydration"],
    }
    raw_ocr = "CONFIDENTIAL CLINICAL REPORT: Full unparsed OCR dump with sensitive text..."

    # save_raw_text defaults to False
    save_report_findings(
        email="patient@example.com",
        findings=findings,
        raw_text=raw_ocr,
        save_raw_text=False,
        db_path=test_db,
    )

    records = fetch_report_findings("patient@example.com", db_path=test_db)
    assert len(records) == 1
    timestamp, saved_findings_json, saved_raw = records[0]

    # Structured findings ARE saved
    parsed = json.loads(saved_findings_json)
    assert parsed["summary"] == "Routine checkup normal"

    # Raw OCR text is NOT saved (None in DB)
    assert saved_raw is None


def test_db_stores_raw_text_only_when_explicitly_requested(test_db):
    """Raw text is stored ONLY when save_raw_text=True is specified."""
    findings = {"summary": "Lab results"}
    raw_ocr = "Raw OCR text line 1, line 2"

    save_report_findings(
        email="patient@example.com",
        findings=findings,
        raw_text=raw_ocr,
        save_raw_text=True,
        db_path=test_db,
    )

    records = fetch_report_findings("patient@example.com", db_path=test_db)
    assert len(records) == 1
    timestamp, saved_findings_json, saved_raw = records[0]
    assert saved_raw == raw_ocr


def test_db_findings_are_sanitized_before_saving(test_db):
    """Control chars, zero-width chars, and oversized fields are sanitized before DB insertion."""
    dirty_findings = {
        "summary": "Test\u200B \x00result" + ("X" * 1000),
        "health_risks": ["Risk\uFEFF 1", "Risk \u202E2"],
    }

    save_report_findings(
        email="patient@example.com",
        findings=dirty_findings,
        db_path=test_db,
    )

    records = fetch_report_findings("patient@example.com", db_path=test_db)
    timestamp, saved_findings_json, _ = records[0]
    saved = json.loads(saved_findings_json)

    assert "\u200B" not in saved["summary"]
    assert "\x00" not in saved["summary"]
    # summary limit is 500
    assert len(saved["summary"]) <= 500
    assert "\uFEFF" not in saved["health_risks"][0]
    assert "\u202E" not in saved["health_risks"][1]


def test_sql_injection_in_findings_prevented(test_db):
    """SQL injection payloads in findings or email cannot break parameterized queries."""
    sqli_payload = "'; DROP TABLE report_findings; --"
    findings = {"summary": sqli_payload, "sql": "OR '1'='1"}

    save_report_findings(
        email=sqli_payload,
        findings=findings,
        db_path=test_db,
    )

    # Table still exists and record can be retrieved
    records = fetch_report_findings(sqli_payload, db_path=test_db)
    assert len(records) == 1
    parsed = json.loads(records[0][1])
    assert parsed["summary"] == sqli_payload

    # Verify table was NOT dropped
    with get_connection(test_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='report_findings'")
        assert cursor.fetchone() is not None

