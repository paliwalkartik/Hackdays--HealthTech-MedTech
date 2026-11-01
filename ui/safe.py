"""
ui/safe.py — Safe HTML rendering and untrusted input sanitization helpers.

Security guarantees:
- Every untrusted string rendered in an unsafe_allow_html=True context MUST go
  through esc() or safe_cell().
- Extracted report data (test names, units, free-text lines) is stripped of
  control characters, zero-width characters, and RTL override markers.
- Table cells are capped at max_cell_len (default 200 chars) and rows at
  max_rows (default 500 rows).
- Untrusted text cannot be used to forge file paths, URLs, or HTML attributes.
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Character filters for untrusted input
# ---------------------------------------------------------------------------

# Dangerous Unicode characters:
# - Zero-width characters: \u200B (ZWSP), \u200C (ZWNJ), \u200D (ZWJ), \u2060 (WJ), \uFEFF (BOM)
# - Bidirectional override & embedding controls: \u200E (LRM), \u200F (RLM), \u202A-\u202E (LRE, RLE, PDF, LRO, RLO),
#   \u2066-\u2069 (LRI, RLI, FSI, PDI), \u061C (ALM)
DANGEROUS_UNICODE_CHARS = re.compile(
    r"[\u200B-\u200D\u200E\u200F\u202A-\u202E\u2060\u2066-\u2069\uFEFF\u061C]"
)

# ASCII and C1 control characters (excluding nothing, or keeping \t, \n, \r when keep_newlines=True)
ASCII_C1_CONTROL_CHARS = re.compile(r"[\x00-\x1F\x7F-\x9F]")
ASCII_C1_EXCEPT_NEWLINES = re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]")

DEFAULT_MAX_CELL_CHARS: int = 200
DEFAULT_MAX_ROWS: int = 500


# ---------------------------------------------------------------------------
# Sanitization & Cleaning Helpers
# ---------------------------------------------------------------------------


def strip_control_chars(text: Any, keep_newlines: bool = False) -> str:
    """Strip ASCII control characters, C1 controls, zero-width, and RTL override characters.

    Parameters
    ----------
    text : string or any object to clean.
    keep_newlines : if True, keeps \\n, \\r, and \\t; otherwise removes all control characters.
    """
    if text is None:
        return ""
    s = str(text)
    # Strip dangerous Unicode characters (zero-width, RTL overrides)
    s = DANGEROUS_UNICODE_CHARS.sub("", s)
    # Strip ASCII and C1 control characters
    pattern = ASCII_C1_EXCEPT_NEWLINES if keep_newlines else ASCII_C1_CONTROL_CHARS
    s = pattern.sub("", s)
    return s.strip()


def cap_length(text: Any, max_len: int = DEFAULT_MAX_CELL_CHARS) -> str:
    """Cap string to max_len characters."""
    if text is None:
        return ""
    s = str(text)
    return s[:max_len]


def cap_rows(rows: Any, max_rows: int = DEFAULT_MAX_ROWS) -> List[Any]:
    """Cap a list or iterable of rows/items to max_rows."""
    if not rows:
        return []
    try:
        return list(rows)[:max_rows]
    except TypeError:
        return []


def sanitize_untrusted_text(
    value: Any,
    max_len: int = DEFAULT_MAX_CELL_CHARS,
    keep_newlines: bool = False,
) -> str:
    """Clean untrusted text: strip control chars, zero-width chars, and cap length.

    Returns clean plain text (un-escaped) safe for database storage or further processing.
    """
    cleaned = strip_control_chars(value, keep_newlines=keep_newlines)
    return cap_length(cleaned, max_len=max_len)


# ---------------------------------------------------------------------------
# HTML Escaping & Rendering Helpers
# ---------------------------------------------------------------------------


def esc(value: Any) -> str:
    """HTML-escape value for safe interpolation into unsafe_allow_html=True blocks.

    - None → empty string.
    - All other values are str()-coerced then html.escape(quote=True).
    """
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def esc_list(values: Any) -> List[str]:
    """Return a list of HTML-escaped strings from an iterable.

    Non-iterable or None yields an empty list.
    """
    if not values:
        return []
    try:
        return [esc(v) for v in values]
    except TypeError:
        return []


def safe_cell(value: Any, max_len: int = DEFAULT_MAX_CELL_CHARS) -> str:
    """Clean, cap, and HTML-escape an untrusted cell value for UI rendering.

    1. Strips control characters, zero-width spaces, and RTL markers.
    2. Caps length to max_len (default 200 chars).
    3. HTML-escapes (quote=True) for safe rendering in HTML.
    """
    clean_text = sanitize_untrusted_text(value, max_len=max_len, keep_newlines=False)
    return esc(clean_text)


def safe_table_rows(
    rows: Any,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_cell_len: int = DEFAULT_MAX_CELL_CHARS,
) -> List[Any]:
    """Clean, cap rows, and HTML-escape all cells for an untrusted table (e.g. lab findings)."""
    if not rows:
        return []
    capped_rows = cap_rows(rows, max_rows=max_rows)
    clean_rows = []
    for row in capped_rows:
        if isinstance(row, dict):
            clean_rows.append(
                {k: safe_cell(v, max_len=max_cell_len) for k, v in row.items()}
            )
        elif isinstance(row, (list, tuple)):
            clean_rows.append(
                [safe_cell(item, max_len=max_cell_len) for item in row]
            )
        else:
            clean_rows.append(safe_cell(row, max_len=max_cell_len))
    return clean_rows


# ---------------------------------------------------------------------------
# URL, Attribute, and Path Safety Helpers
# ---------------------------------------------------------------------------


def safe_picture_url(url: Any) -> str:
    """Validate and HTML-escape a picture URL.

    Only https:// URLs are allowed (Google profile photos are always https).
    http:// and any other scheme are rejected and return "".
    """
    if url is None:
        return ""
    clean = str(url).strip()
    if clean.startswith("https://"):
        return html.escape(clean, quote=True)
    return ""


def safe_url(url: Any) -> str:
    """Validate an untrusted URL, ensuring only safe http:// or https:// schemes.

    Rejects javascript:, data:, vbscript:, file:, and relative URLs.
    Strips control characters and returns an HTML-escaped safe URL or empty string.
    """
    if url is None:
        return ""
    clean = strip_control_chars(str(url))
    clean_lower = clean.lower()
    if clean_lower.startswith(("http://", "https://")):
        # Reject if contains javascript pseudo-protocol obfuscation
        if "javascript:" in clean_lower or "vbscript:" in clean_lower or "data:" in clean_lower:
            return ""
        return html.escape(clean, quote=True)
    return ""


def safe_html_attr(value: Any, max_len: int = DEFAULT_MAX_CELL_CHARS) -> str:
    """Sanitize and escape a string intended for use inside an HTML attribute.

    Strips control characters, newlines, and quotes, and caps length.
    """
    if value is None:
        return ""
    clean = sanitize_untrusted_text(value, max_len=max_len, keep_newlines=False)
    return html.escape(clean, quote=True)


def safe_filename_component(name: Any) -> str:
    """Sanitize an untrusted name so it cannot be used for path traversal or malicious file naming.

    Removes directory traversal sequences (..), slashes, backslashes, null bytes,
    and control characters. Returns a clean alphanumeric basename (max 64 chars).
    """
    if not name:
        return "report_file"
    s = strip_control_chars(str(name))
    # Replace directory separators and null bytes
    s = s.replace("/", "_").replace("\\", "_").replace("\x00", "")
    # Remove path traversal sequences
    while ".." in s:
        s = s.replace("..", "_")
    # Retain only safe characters: alphanumeric, dot, underscore, dash
    s = re.sub(r"[^A-Za-z0-9._-]", "_", s)
    s = s.strip("._")
    return s[:64] if s else "report_file"


# ---------------------------------------------------------------------------
# Structured Findings Sanitization
# ---------------------------------------------------------------------------


def sanitize_report_findings(
    findings: Any,
    max_cell_len: int = DEFAULT_MAX_CELL_CHARS,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> Dict[str, Any]:
    """Validate and sanitize a structured report findings dictionary.

    - Strips control characters, zero-width characters, and RTL overrides from all fields.
    - Caps text field lengths (cells/tests/units at max_cell_len; free-text summary up to 500 chars).
    - Caps list lengths to max_rows (default 500).
    - Returns clean dictionary suitable for database storage and rendering.
    """
    if not isinstance(findings, dict):
        return {}

    sanitized: Dict[str, Any] = {}
    for key, value in findings.items():
        clean_key = sanitize_untrusted_text(key, max_len=64)
        if isinstance(value, str):
            # Allow longer limits for narrative fields (summary, action_plan, visual_observations)
            limit = 500 if clean_key in ("summary", "visual_observations", "action_plan") else max_cell_len
            sanitized[clean_key] = sanitize_untrusted_text(value, max_len=limit, keep_newlines=True)
        elif isinstance(value, list):
            capped_items = cap_rows(value, max_rows=max_rows)
            clean_items = []
            for item in capped_items:
                if isinstance(item, str):
                    clean_items.append(sanitize_untrusted_text(item, max_len=max_cell_len))
                elif isinstance(item, dict):
                    clean_items.append(
                        {
                            sanitize_untrusted_text(k, max_len=64): sanitize_untrusted_text(v, max_len=max_cell_len)
                            for k, v in item.items()
                        }
                    )
                else:
                    clean_items.append(item)
            sanitized[clean_key] = clean_items
        elif isinstance(value, (int, float, bool)):
            sanitized[clean_key] = value
        elif value is None:
            sanitized[clean_key] = None
        else:
            sanitized[clean_key] = sanitize_untrusted_text(str(value), max_len=max_cell_len)

    return sanitized
