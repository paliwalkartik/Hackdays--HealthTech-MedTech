"""
ui/sidebar.py — Sidebar Navigation, User Profile, OAuth Login, and Emergency SOS
"""

from __future__ import annotations

import webbrowser
import streamlit as st
from streamlit_js_eval import get_geolocation

from auth import (
    dev_login,
    get_current_user,
    get_safe_user_profile,
    is_auth_configured,
    is_dev_mode,
    is_logged_in,
    login,
    logout,
)
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

        if not is_logged_in():
            if is_dev_mode():
                st.warning("⚠️ **DEV MODE ACTIVE**\nAuth bypass enabled")
                if st.button("🔑 Dev Login (Bypass)", key="sidebar_dev_login", use_container_width=True):
                    dev_login()
                    st.rerun()
            elif is_auth_configured():
                st.markdown(
                    "<p style='color:#9CA3AF;font-size:13px;text-align:center;'>Sign in to access your health dashboard</p>",
                    unsafe_allow_html=True,
                )
                if st.button("🔐 Sign in with Google", key="sidebar_google_login", use_container_width=True):
                    login()
            else:
                st.markdown(
                    """
                <div style='padding:12px;background:rgba(59,130,246,0.1);border:1px solid rgba(59,130,246,0.25);
                            border-radius:8px;font-size:12px;color:#9CA3AF;text-align:center;'>
                    <div style='color:#60A5FA;font-weight:600;margin-bottom:4px;'>ℹ️ Auth Setup Required</div>
                    Configure <code>.streamlit/secrets.toml</code> or set <code>IV_DEV_LOGIN=1</code>.
                </div>""",
                    unsafe_allow_html=True,
                )
        else:
            user = get_current_user() or {}
            profile = get_safe_user_profile(user)
            name = profile["name"]
            email = profile["email"]
            picture = profile["picture"]

            if is_dev_mode():
                st.markdown(
                    """
                <div style='text-align:center;margin-bottom:8px;'>
                  <span style='background:rgba(234,179,8,0.2);color:#EAB308;padding:2px 8px;
                               border-radius:4px;font-size:11px;font-weight:600;'>DEV MODE ACTIVE</span>
                </div>""",
                    unsafe_allow_html=True,
                )

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
            if st.button("🚪 Log Out", key="sidebar_logout_btn", use_container_width=True):
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
                padding-top:20px;text-align:center;'>
      <div style='font-size:80px;filter:drop-shadow(0 0 30px #00C9FF88);'>🫀</div>
      <h1 style='font-size:38px;font-weight:700;background:linear-gradient(135deg,#00C9FF,#0066FF);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:12px 0 6px;'>
        Intelli-Vitals
      </h1>
      <p style='color:#9CA3AF;font-size:16px;max-width:520px;line-height:1.5;margin:0 0 20px;'>
        Touchless Health Monitoring & AI-Powered Clinical Triage Assistant
      </p>
    </div>""",
        unsafe_allow_html=True,
    )

    if is_dev_mode():
        st.markdown(
            """
        <div style='max-width:560px;margin:0 auto 20px;padding:16px;background:rgba(234,179,8,0.1);
                    border:1px solid rgba(234,179,8,0.4);border-radius:12px;text-align:center;'>
            <div style='font-size:16px;font-weight:700;color:#EAB308;letter-spacing:0.5px;'>
                ⚠️ DEV MODE ACTIVE
            </div>
            <p style='color:#D1D5DB;font-size:13px;margin:8px 0 12px;'>
                Local authentication bypass is enabled via <code>IV_DEV_LOGIN=1</code>. Click below to enter the dashboard.
            </p>
        </div>""",
            unsafe_allow_html=True,
        )
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔑 Log in with Dev Mode Bypass", key="wall_dev_login", use_container_width=True):
                dev_login()
                st.rerun()

    elif is_auth_configured():
        st.markdown(
            """
        <div style='max-width:480px;margin:0 auto 16px;text-align:center;'>
            <p style='color:#9CA3AF;font-size:14px;margin-bottom:12px;'>
                Sign in to access your health dashboard
            </p>
        </div>""",
            unsafe_allow_html=True,
        )
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔐 Sign in with Google", key="wall_google_login", use_container_width=True):
                login()

    else:
        st.markdown(
            """
        <div style='max-width:620px;margin:0 auto 24px;padding:20px;background:rgba(59,130,246,0.08);
                    border:1px solid rgba(59,130,246,0.3);border-radius:12px;text-align:left;'>
            <div style='font-size:16px;font-weight:700;color:#60A5FA;margin-bottom:8px;'>
                ℹ️ Authentication Setup Required
            </div>
            <p style='color:#D1D5DB;font-size:13px;line-height:1.6;margin-bottom:12px;'>
                Sign in to access your health dashboard. Streamlit OpenID Connect (OIDC) authentication requires credentials in <code>.streamlit/secrets.toml</code>.
            </p>
            <ol style='color:#9CA3AF;font-size:13px;line-height:1.6;margin-left:18px;margin-bottom:12px;'>
                <li>Copy <code>.streamlit/secrets.toml.example</code> to <code>.streamlit/secrets.toml</code></li>
                <li>Add your Google Cloud OAuth Client ID, Client Secret, and a <code>cookie_secret</code></li>
                <li>Set Authorized redirect URI in Google Cloud Console to: <code>http://localhost:8501/oauth2callback</code></li>
            </ol>
            <div style='border-top:1px solid rgba(255,255,255,0.08);padding-top:10px;margin-top:10px;color:#9CA3AF;font-size:12px;'>
                💡 <b>Offline / Local Testing:</b> Set <code>IV_DEV_LOGIN=1</code> in your environment or <code>.env</code> file to bypass login with Dev Mode.
            </div>
        </div>""",
            unsafe_allow_html=True,
        )

    # Feature badges
    st.markdown(
        """
    <div style='margin-top:20px;display:flex;gap:24px;flex-wrap:wrap;justify-content:center;'>
      <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                  border-radius:12px;padding:16px 24px;text-align:center;min-width:140px;'>
        <div style='font-size:26px;'>💓</div>
        <div style='color:#9CA3AF;font-size:13px;margin-top:6px;'>rPPG Heart Rate</div>
      </div>
      <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                  border-radius:12px;padding:16px 24px;text-align:center;min-width:140px;'>
        <div style='font-size:26px;'>🔬</div>
        <div style='color:#9CA3AF;font-size:13px;margin-top:6px;'>Report Analysis</div>
      </div>
      <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                  border-radius:12px;padding:16px 24px;text-align:center;min-width:140px;'>
        <div style='font-size:26px;'>📋</div>
        <div style='color:#9CA3AF;font-size:13px;margin-top:6px;'>Health History</div>
      </div>
    </div>""",
        unsafe_allow_html=True,
    )
