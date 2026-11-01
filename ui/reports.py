"""
ui/reports.py — Tab 3: Medical Report Upload, Analysis, and Hospital Recommendations
"""

from __future__ import annotations

import requests
import streamlit as st

from config import config
from hospitals import get_hospitals_for_specialty
from ui.safe import esc


def render_reports_tab() -> None:
    """Render medical report analysis upload and hospital suggestion cards."""
    st.markdown("<div class='label-sm'>Medical Report Analysis</div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#9CA3AF;font-size:13px;margin-bottom:20px;'>"
        "Upload a PDF or image report. Gemini analyzes it alongside your live webcam appearance.</p>",
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Upload Medical Report",
        type=["pdf", "jpg", "jpeg", "png"],
        label_visibility="collapsed",
    )

    if uploaded_file:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.success(f"✅ {uploaded_file.name} ({uploaded_file.size/1024:.1f} KB)")
        with c2:
            analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
        if analyze_btn:
            with st.spinner("📤 Uploading to Gemini File API... (10-20 seconds)"):
                try:
                    res = requests.post(
                        f"{config.API_BASE_URL}/analyze_report",
                        files={
                            "file": (
                                uploaded_file.name,
                                uploaded_file.getvalue(),
                                uploaded_file.type,
                            )
                        },
                        headers=config.api_headers,
                        timeout=120,
                    )
                    if res.status_code == 200:
                        r = res.json()
                        if "error" in r:
                            st.error(r["error"])
                        else:
                            st.session_state["last_analysis"] = r
                            urgency = r.get("urgency_level", "Routine")
                            uc = {
                                "Urgent": "#FF1744",
                                "Soon": "#FF6D00",
                                "Routine": "#00E676",
                            }.get(urgency, "#888")
                            safe_urgency = esc(urgency)
                            safe_summary = esc(r.get("summary", ""))
                            st.markdown(
                                f"""
                            <div class="urgency-badge" style="background:rgba(0,0,0,0.3);border-color:{uc};">
                                <span style="color:{uc};font-weight:700;">⚠ {safe_urgency}</span>
                                <span style="color:#D1D5DB;margin-left:12px;">{safe_summary}</span>
                            </div>""",
                                unsafe_allow_html=True,
                            )
                            ca, cb = st.columns(2)
                            with ca:
                                st.markdown("**🏥 Specialty**")
                                st.info(r.get("medical_specialty", "N/A"))
                                st.markdown("**👁 Visual Observations**")
                                st.write(r.get("visual_observations", "N/A"))
                                st.markdown("**⚕ Action Plan**")
                                st.write(r.get("action_plan", "N/A"))
                            with cb:
                                st.markdown("**⚠ Health Risks**")
                                for risk in r.get("health_risks", []):
                                    st.markdown(f"• {esc(risk)}")
                                st.markdown("**🌿 Lifestyle Measures**")
                                for m in r.get("lifestyle_measures", []):
                                    st.markdown(f"• {esc(m)}")
                    else:
                        st.error(f"Backend error {res.status_code}")
                except Exception as ex:
                    st.error(f"Connection error: {ex}")
    else:
        st.markdown(
            """
        <div style='border:2px dashed rgba(0,201,255,0.2);border-radius:16px;
                    padding:60px 20px;text-align:center;color:#374151;margin-top:10px;'>
            <div style='font-size:56px;'>📄</div>
            <p style='color:#6B7280;font-size:15px;margin-top:12px;'>
                Drop a PDF, JPG, or PNG medical report above
            </p>
            <p style='color:#374151;font-size:12px;'>
                Gemini will cross-reference it with your live camera feed
            </p>
        </div>""",
            unsafe_allow_html=True,
        )

    # ── Hospital Recommendations (persists after analysis via session_state) ───
    if "last_analysis" in st.session_state:
        r = st.session_state["last_analysis"]
        specialty = r.get("medical_specialty", "General")
        hospitals = get_hospitals_for_specialty(specialty)

        safe_specialty = esc(specialty)
        st.markdown(
            "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:28px 0 20px;'>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
        <div style='margin-bottom:16px;'>
            <div style='font-size:11px;color:#6B7280;font-weight:600;letter-spacing:1px;
                        text-transform:uppercase;margin-bottom:4px;'>Recommended Specialists</div>
            <div style='font-size:18px;font-weight:700;color:#F9FAFB;'>
                Top 3 <span style='color:#00C9FF;'>{safe_specialty}</span> Hospitals in Bhopal
            </div>
        </div>""",
            unsafe_allow_html=True,
        )

        for i, h in enumerate(hospitals[:3]):
            col_card, col_btn = st.columns([4, 1], gap="small")
            h_name = esc(str(h["name"]))
            h_area = esc(str(h["area"]))
            h_phone = esc(str(h["phone"]))
            h_rating = esc(str(h["rating"]))
            h_beds = esc(str(h["beds"]))
            h_icon = esc(str(h["icon"]))

            with col_card:
                st.markdown(
                    f"""
                <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                            border-left:3px solid #00C9FF;border-radius:14px;
                            padding:16px 20px;display:flex;align-items:center;gap:16px;
                            margin-bottom:10px;'>
                    <div style='font-size:36px;'>{h_icon}</div>
                    <div style='flex:1;'>
                        <div style='font-weight:700;font-size:15px;color:#F9FAFB;'>{h_name}</div>
                        <div style='font-size:12px;color:#6B7280;margin-top:3px;'>📍 {h_area}</div>
                        <div style='display:flex;gap:16px;margin-top:6px;'>
                            <span style='font-size:12px;color:#9CA3AF;'>{h_rating}</span>
                            <span style='font-size:12px;color:#9CA3AF;'>🛏 {h_beds} beds</span>
                            <span style='font-size:12px;color:#4B5563;'>📞 {h_phone}</span>
                        </div>
                    </div>
                </div>""",
                    unsafe_allow_html=True,
                )
            with col_btn:
                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                if st.button("📞 Contact", key=f"call_h_{i}", use_container_width=True):
                    st.toast(f"📞 Calling {h['name']} at {h['phone']}…", icon="🏥")

