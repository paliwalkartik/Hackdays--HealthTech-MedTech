"""
ui/records.py — Tab 2: Patient Health History and Past Records
"""

from __future__ import annotations

import html
import json
import pandas as pd
import streamlit as st

from db import fetch_logs


def render_records_tab(email: str) -> None:
    """Render past vital sign readings and clinical summaries."""
    st.markdown("<div class='label-sm'>Your Health History</div>", unsafe_allow_html=True)
    records = fetch_logs(email)
    if records:
        formatted = []
        for r in records:
            try:
                d = json.loads(r[2])
                status = d.get("clinical_status", "N/A")
                rec = d.get("recommendation", "N/A")
            except Exception:
                status = rec = "N/A"
            formatted.append(
                {
                    "📅 Timestamp": r[0],
                    "💓 BPM": f"{r[1]:.1f}",
                    "🏥 Status": status,
                    "💡 Recommendation": rec,
                }
            )
        df = pd.DataFrame(formatted)
        safe_email = html.escape(email)
        st.markdown(
            f"<p style='color:#6B7280;font-size:13px;margin-bottom:12px;'>"
            f"{len(formatted)} record(s) found for {safe_email}</p>",
            unsafe_allow_html=True,
        )
        st.dataframe(df, use_container_width=True, height=400)
    else:
        st.markdown(
            """
        <div style='text-align:center;padding:60px 20px;color:#374151;'>
            <div style='font-size:48px;'>📭</div>
            <p style='margin-top:12px;font-size:15px;'>No records yet. Generate a Clinical Snapshot to save your first entry.</p>
        </div>""",
            unsafe_allow_html=True,
        )

