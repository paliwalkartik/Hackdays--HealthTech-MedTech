"""
db.py — Context-managed SQLite Database Access for Health Records
"""

from __future__ import annotations

import contextlib
import sqlite3
from typing import Any, Generator, List, Tuple

from config import config


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
    """Initialize heart_rate_logs table if it does not already exist."""
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


def save_log(email: str, bpm: float, analysis: str, db_path: str | None = None) -> None:
    """Save a patient vital sign and clinical analysis log record."""
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO heart_rate_logs (username, bpm, analysis) VALUES (?, ?, ?)",
            (email, float(bpm), str(analysis)),
        )


def fetch_logs(email: str, db_path: str | None = None) -> List[Tuple[Any, ...]]:
    """Fetch all history records for a patient ordered newest first."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, bpm, analysis FROM heart_rate_logs WHERE username = ? ORDER BY timestamp DESC",
            (email,),
        )
        return cursor.fetchall()

