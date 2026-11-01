"""
db.py — Context-managed SQLite Database Access for Health Records
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from config import config
from ui.safe import sanitize_report_findings


@contextlib.contextmanager
def get_connection(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context-managed connection ensuring transactions commit and connections close cleanly."""
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: str | None = None) -> None:
    """Initialize database tables if they do not already exist."""
    with get_connection(db_path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS heart_rate_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                bpm REAL,
                analysis TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS report_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                findings TEXT,
                raw_text TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )"""
        )


def save_log(email: str, bpm: float, analysis: str, db_path: str | None = None) -> None:
    """Save a patient vital sign and clinical analysis log record."""
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO heart_rate_logs (username, bpm, analysis) VALUES (?, ?, ?)",
            (email, float(bpm), str(analysis)),
        )


def fetch_logs(email: str, db_path: str | None = None) -> List[Tuple[Any, ...]]:
    """Fetch all vital history records for a patient ordered newest first."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, bpm, analysis FROM heart_rate_logs WHERE username = ? ORDER BY timestamp DESC",
            (email,),
        )
        return cursor.fetchall()


def save_report_findings(
    email: str,
    findings: Union[Dict[str, Any], str],
    raw_text: Optional[str] = None,
    save_raw_text: bool = False,
    db_path: str | None = None,
) -> None:
    """Store only structured, validated findings in the DB, not raw OCR text unless requested.

    Parameters
    ----------
    email : Patient identifier (e.g. email or user ID).
    findings : Dict or JSON string of structured findings.
    raw_text : Optional raw OCR or unparsed text. Discarded unless save_raw_text=True.
    save_raw_text : Whether the user explicitly chose to 'save original text'.
    db_path : Optional path to sqlite database.
    """
    if isinstance(findings, dict):
        clean_findings = sanitize_report_findings(findings)
        findings_json = json.dumps(clean_findings)
    else:
        findings_json = str(findings)

    # Store raw text only when user explicitly chose to save original text
    stored_raw: Optional[str] = str(raw_text) if (save_raw_text and raw_text is not None) else None

    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO report_findings (username, findings, raw_text) VALUES (?, ?, ?)",
            (email, findings_json, stored_raw),
        )


def fetch_report_findings(email: str, db_path: str | None = None) -> List[Tuple[Any, ...]]:
    """Fetch all report findings history for a patient ordered newest first."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, findings, raw_text FROM report_findings WHERE username = ? ORDER BY timestamp DESC",
            (email,),
        )
        return cursor.fetchall()
