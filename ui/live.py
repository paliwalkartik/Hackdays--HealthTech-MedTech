"""
ui/live.py — Tab 1: Real-Time Patient Camera Feed, Vitals Telemetry, and Polling Loop
"""

from __future__ import annotations

import json
import time
import pandas as pd
import requests
import streamlit as st

from config import config
from db import save_log
from ui.safe import esc


def render_live_ui(email: str) -> tuple[st.delta_generator.DeltaGenerator, st.delta_generator.DeltaGenerator]:
    """Render Tab 1 controls and return placeholders for real-time telemetry updates."""
    col1, col2 = st.columns([1.1, 0.9], gap="large")

    with col1:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("<div class='label-sm'>Patient Camera Feed</div>", unsafe_allow_html=True)
        st.markdown(
            f'<img src="{config.API_BASE_URL}/video_feed?token={config.api_token}" width="100%" '
            'style="border-radius:12px;border:1px solid rgba(255,255,255,0.1);">',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("<div class='label-sm'>🤖 Gemini Clinical Snapshot</div>", unsafe_allow_html=True)
        st.markdown(
            "<p style='color:#9CA3AF;font-size:13px;'>AI analysis of vitals + facial appearance</p>",
            unsafe_allow_html=True,
        )
        if st.button("⚡ Generate Clinical Snapshot", key="snapshot_btn"):
            with st.spinner("Analyzing vitals and facial data via Gemini..."):
                try:
                    res = requests.get(f"{config.API_BASE_URL}/consult", headers=config.api_headers, timeout=60)
                    if res.status_code == 200:
                        data = res.json()
                        if "error" in data:
                            st.error(data["error"])
                        else:
                            avg_bpm = data.get("average_bpm", 0)
                            save_log(email, avg_bpm, json.dumps(data))
                            st.success("✅ Snapshot saved to your records")
                            st.markdown(
                                f"""
                            <div class="snapshot-box">
                                <div style='font-weight:600;color:#00C9FF;margin-bottom:10px;'>
                                    {esc(data.get('clinical_status','N/A'))}
                                </div>
                                <p style='color:#D1D5DB;margin:6px 0;'>
                                    <strong style='color:#9CA3AF;'>Avg BPM:</strong> {avg_bpm}
                                </p>
                                <p style='color:#D1D5DB;margin:6px 0;'>
                                    <strong style='color:#9CA3AF;'>Visual:</strong> {esc(data.get('visual_assessment','N/A'))}
                                </p>
                                <p style='color:#D1D5DB;margin:6px 0;'>
                                    <strong style='color:#9CA3AF;'>Recommendation:</strong> {esc(data.get('recommendation','N/A'))}
                                </p>
                            </div>""",
                                unsafe_allow_html=True,
                            )
                    else:
                        st.error("Failed to reach backend")
                except Exception as e:
                    st.error(f"Backend error: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        meas_col1, meas_col2 = st.columns([2, 1])
        with meas_col1:
            st.markdown("<div class='label-sm'>Vitals Telemetry</div>", unsafe_allow_html=True)
        with meas_col2:
            if st.button("🔄 New Reading", key="reset_btn"):
                try:
                    requests.post(f"{config.API_BASE_URL}/reset_vitals", headers=config.api_headers, timeout=3)
                    if "pulse_data" in st.session_state:
                        st.session_state.pulse_data = []
                    st.success("Ready for new reading!")
                except Exception:
                    pass

        bpm_placeholder = st.empty()
        chart_placeholder = st.empty()

    return bpm_placeholder, chart_placeholder


def run_live_polling(
    bpm_placeholder: st.delta_generator.DeltaGenerator,
    chart_placeholder: st.delta_generator.DeltaGenerator,
    max_iterations: int | None = None,
) -> None:
    """Continuously poll backend for vitals and update telemetry UI in real-time."""
    if "pulse_data" not in st.session_state:
        st.session_state.pulse_data = []

    if max_iterations is None and config.IV_DISABLE_POLLING:
        max_iterations = 1

    iterations = 0
    while True:
        if max_iterations is not None and iterations >= max_iterations:
            break
        iterations += 1
        try:
            res = requests.get(f"{config.API_BASE_URL}/vitals", headers=config.api_headers, timeout=1)
            if res.status_code == 200:
                data = res.json()
                bpm = data.get("bpm", 0)
                pulse = data.get("pulse", 0)
                is_stable = data.get("is_stable", False)
                is_completed = data.get("is_completed", False)
                stable_dur = data.get("stable_duration", 0.0)

                st.session_state.pulse_data.append(pulse)
                if len(st.session_state.pulse_data) > 120:
                    st.session_state.pulse_data.pop(0)

                pct = min(100, int((stable_dur / config.MEASURE_SECONDS) * 100))
                secs = max(0, int(config.MEASURE_SECONDS - stable_dur))

                if is_completed:
                    bpm_html = f"<div class='bpm-number'>{bpm:.0f}</div>"
                    timer_html = "<div style='font-size:20px;color:#00E676;font-weight:600;'>✓ Complete</div>"
                    bar_color = "#00E676"
                elif is_stable:
                    bpm_html = f"<div class='bpm-number'>{bpm:.0f}</div>"
                    timer_html = f"<div style='font-size:32px;font-weight:700;color:#00C9FF;'>{secs}s</div>"
                    bar_color = "#00C9FF"
                else:
                    bpm_html = "<div class='bpm-inactive'>---</div>"
                    timer_html = "<div style='font-size:14px;color:#6B7280;'>Center face in box</div>"
                    bar_color = "#374151"

                bpm_placeholder.markdown(
                    f"""
                <div style='display:flex;gap:16px;margin-bottom:16px;'>
                  <div class='metric-card' style='flex:1;'>
                    <div class='label-sm'>Heart Rate</div>
                    {bpm_html}
                    <div style='font-size:12px;color:#6B7280;margin-top:4px;'>BPM</div>
                  </div>
                  <div class='metric-card' style='flex:1;'>
                    <div class='label-sm'>Time Remaining</div>
                    {timer_html}
                    <div style='background:#1F2937;border-radius:99px;height:6px;margin-top:12px;overflow:hidden;'>
                      <div style='width:{pct}%;background:{bar_color};height:100%;
                           border-radius:99px;transition:width 0.3s ease;'></div>
                    </div>
                  </div>
                </div>""",
                    unsafe_allow_html=True,
                )

                chart_placeholder.line_chart(
                    pd.DataFrame({"Pulse Wave": st.session_state.pulse_data}),
                    height=280,
                    use_container_width=True,
                )
        except Exception:
            pass
        time.sleep(0.1)

