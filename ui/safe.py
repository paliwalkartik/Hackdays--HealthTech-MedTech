"""
ui/safe.py — Safe HTML rendering helpers for Streamlit unsafe_allow_html contexts.

Every user-provided or model-provided string that is interpolated into an
unsafe_allow_html=True block MUST go through esc() before use.
"""

from __future__ import annotations

import html
from typing import Any


def esc(value: Any) -> str:
    """HTML-escape value for safe interpolation into unsafe_allow_html=True blocks.

    - None → empty string.
    - All other values are str()-coerced then html.escape(quote=True).
    """
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def esc_list(values: Any) -> list[str]:
    """Return a list of HTML-escaped strings from an iterable.

    Non-iterable or None yields an empty list.
    """
    if not values:
        return []
    try:
        return [esc(v) for v in values]
    except TypeError:
        return []


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

