"""
ui/sidebar.py — Sidebar Navigation, User Profile, OAuth Login, and Emergency SOS
"""

from __future__ import annotations

import html
import os
import webbrowser
import streamlit as st
from streamlit_js_eval import get_geolocation

from auth import CREDENTIALS_FILE, get_auth_url, logout
from ui.styles import apply_sos_styles


def render_sidebar() -> None:
    """Render the application sidebar with authentication and SOS controls."""
    with st.sidebar:
        st.markdown(
            """
        <div style='text-align:center;padding:20px 0 10px;'>
            <div style='font-size:36px;'>🫀</div>
            <div style='font-size:18px;font-weight:700;color:#00C9FF;letter-spacing:1px;'>INTELLI-VITALS</div>
            <div style='font-size:11px;color:#4B5563;margin-top:4px;'>Touchless Health Monitoring</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
        st.markdown(
            "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:0 0 16px;'>",
            unsafe_allow_html=True,
        )

        if not st.session_state.get("connected"):
            st.markdown(
                "<p style='color:#9CA3AF;font-size:13px;text-align:center;'>Sign in to access your health dashboard</p>",
                unsafe_allow_html=True,
            )
            if os.path.exists(CREDENTIALS_FILE):
                auth_url = get_auth_url()
                st.markdown(
                    f"""
                <a href="{auth_url}" target="_self" style="text-decoration:none;">
                  <div style="display:flex;align-items:center;justify-content:center;gap:10px;
                       background:linear-gradient(135deg,#00C9FF,#0066FF);color:white;
                       border-radius:10px;padding:12px 20px;font-weight:600;font-size:14px;
                       cursor:pointer;margin-top:8px;transition:opacity 0.2s;">
                    <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Google_%22G%22_logo.svg/768px-Google_%22G%22_logo.svg.png"
                         width="18" height="18" style="background:white;border-radius:3px;padding:2px;">
                    Sign in with Google
                  </div>
                </a>""",
                    unsafe_allow_html=True,
                )
            else:
                st.error("google_credentials.json missing")
        else:
            user_info = st.session_state.get("user_info", {})
            name = html.escape(user_info.get("name", "User"))
            email = html.escape(user_info.get("email", ""))
            picture = user_info.get("picture", "")
            if picture:
                st.markdown(
                    f"""
                <div style='text-align:center;margin-bottom:12px;'>
                  <img src="{picture}" width="72" height="72"
                       style="border-radius:50%;border:3px solid #00C9FF;box-shadow:0 0 20px rgba(0,201,255,0.3);">
                </div>""",
                    unsafe_allow_html=True,
                )
            st.markdown(
                f"""
            <div style='text-align:center;margin-bottom:16px;'>
              <div style='font-weight:600;font-size:15px;color:#F9FAFB;'>{name}</div>
              <div style='font-size:12px;color:#6B7280;margin-top:4px;'>{email}</div>
            </div>""",
                unsafe_allow_html=True,
            )

            st.markdown(
                "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:0 0 16px;'>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p style='font-size:11px;color:#4B5563;text-align:center;'>SESSION ACTIVE</p>",
                unsafe_allow_html=True,
            )
            if st.button("🚪 Log Out", use_container_width=True):
                logout()

            # ── EMERGENCY SOS ────────────────────────────────────────────
            st.markdown(
                "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:16px 0;'>",
                unsafe_allow_html=True,
            )
            apply_sos_styles()
            st.markdown("<div class='sos-wrapper'>", unsafe_allow_html=True)

            sos_clicked = st.button("🚨  EMERGENCY SOS", key="sos_btn", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown(
                "<p style='font-size:10px;color:#6B7280;text-align:center;margin-top:4px;'>Dispatches ambulance & opens nearest hospital</p>",
                unsafe_allow_html=True,
            )

            if sos_clicked:
                st.session_state["sos_active"] = True

            if st.session_state.get("sos_active"):
                with st.spinner("📡 Acquiring GPS location..."):
                    loc = get_geolocation()

                if loc and loc.get("coords"):
                    lat = loc["coords"]["latitude"]
                    lng = loc["coords"]["longitude"]

                    # High-priority alert
                    st.markdown(
                        f"""
                    <div style='background:linear-gradient(135deg,#B71C1C,#7F0000);
                                border:2px solid #FF1744;border-radius:12px;
                                padding:16px;margin-top:12px;text-align:center;'>
                        <div style='font-size:22px;'>🚑</div>
                        <div style='color:#FF8A80;font-weight:800;font-size:13px;
                                    letter-spacing:1px;margin:6px 0 2px;'>AMBULANCE DISPATCHED TO:</div>
                        <div style='color:white;font-weight:700;font-size:14px;'>
                            {lat:.5f}, {lng:.5f}
                        </div>
                    </div>""",
                        unsafe_allow_html=True,
                    )

                    # Open Google Maps nearest hospital in browser
                    maps_url = f"https://www.google.com/maps/search/hospital/@{lat},{lng},14z"
                    webbrowser.open(maps_url)

                    if st.button("✅ Cancel SOS", key="cancel_sos"):
                        st.session_state["sos_active"] = False
                        st.rerun()
                else:
                    st.warning("⚠ Could not get location. Please allow browser location access and try again.")
                    st.session_state["sos_active"] = False


def render_login_wall() -> None:
    """Render the central welcome screen / login wall when unauthenticated."""
    st.markdown(
        """
    <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;
                min-height:70vh;text-align:center;'>
      <div style='font-size:96px;filter:drop-shadow(0 0 40px #00C9FF88);'>🫀</div>
      <h1 style='font-size:42px;font-weight:700;background:linear-gradient(135deg,#00C9FF,#0066FF);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:16px 0 8px;'>
        Intelli-Vitals
      </h1>
      <p style='color:#6B7280;font-size:18px;max-width:480px;line-height:1.6;'>
        AI-powered touchless health monitoring. Sign in with your Google account to begin.
      </p>
      <div style='margin-top:40px;display:flex;gap:32px;flex-wrap:wrap;justify-content:center;'>
        <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px;padding:20px 28px;text-align:center;min-width:140px;'>
          <div style='font-size:28px;'>💓</div>
          <div style='color:#9CA3AF;font-size:13px;margin-top:6px;'>rPPG Heart Rate</div>
        </div>
        <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px;padding:20px 28px;text-align:center;min-width:140px;'>
          <div style='font-size:28px;'>🔬</div>
          <div style='color:#9CA3AF;font-size:13px;margin-top:6px;'>Report Analysis</div>
        </div>
        <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                    border-radius:12px;padding:20px 28px;text-align:center;min-width:140px;'>
          <div style='font-size:28px;'>📋</div>
          <div style='color:#9CA3AF;font-size:13px;margin-top:6px;'>Health History</div>
        </div>
      </div>
    </div>""",
        unsafe_allow_html=True,
    )
