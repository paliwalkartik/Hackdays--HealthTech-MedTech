"""
hospitals.py — Hospital Data Loader and Lookup Service
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

DATA_FILE = Path(__file__).resolve().parent / "data" / "hospitals.json"

DEFAULT_HOSPITALS: List[Dict[str, Any]] = [
    {
        "name": "AIIMS Bhopal",
        "area": "Saket Nagar, Bhopal",
        "phone": "+91-755-2672354",
        "rating": "⭐ 4.8",
        "beds": "960+",
        "icon": "🏛",
    },
    {
        "name": "Bansal Hospital",
        "area": "Shahpura, Bhopal",
        "phone": "+91-755-4000000",
        "rating": "⭐ 4.6",
        "beds": "350+",
        "icon": "🏥",
    },
    {
        "name": "People's Hospital",
        "area": "Bhanpur, Bhopal",
        "phone": "+91-755-4077777",
        "rating": "⭐ 4.5",
        "beds": "700+",
        "icon": "🏨",
    },
]


def load_hospitals() -> Dict[str, List[Dict[str, Any]]]:
    """Load hospital database from data/hospitals.json with graceful fallback."""
    if DATA_FILE.is_file():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


HOSPITAL_DB: Dict[str, List[Dict[str, Any]]] = load_hospitals()


def get_hospitals_for_specialty(specialty: str) -> List[Dict[str, Any]]:
    """Return matching hospitals for a medical specialty, falling back to top general hospitals."""
    matched_key = next(
        (k for k in HOSPITAL_DB if k.lower() in specialty.lower() or specialty.lower() in k.lower()),
        None,
    )
    return HOSPITAL_DB.get(matched_key) or DEFAULT_HOSPITALS

