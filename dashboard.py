"""
dashboard.py — Streamlit UI: Page Config, Wiring, and Tab Composition
"""

import streamlit as st

from auth import get_current_user, get_safe_user_profile, is_dev_mode, is_logged_in
from db import init_db
from ui.live import render_live_ui, run_live_polling
from ui.records import render_records_tab
from ui.reports import render_reports_tab
from ui.sidebar import render_login_wall, render_sidebar
from ui.styles import apply_global_styles

# Initialize database schema
init_db()

# Page Setup
st.set_page_config(layout="wide", page_title="Intelli-Vitals", page_icon="🫀")

# Apply Global CSS styles
apply_global_styles()

# Authentication & Sidebar
render_sidebar()

# Login Wall for unauthenticated users
if not is_logged_in():
    render_login_wall()
    st.stop()

# Authenticated View
user = get_current_user() or {}
profile = get_safe_user_profile(user)
email = profile["email"]
first_name = profile["first_name"]

if is_dev_mode():
    st.warning("⚠️ **DEV MODE ACTIVE**: Running with local authentication bypass (`IV_DEV_LOGIN=1`). Do not use in production.")

st.markdown(
    f"""
<div style='margin-bottom:24px;'>
  <h1 style='font-size:28px;font-weight:700;color:#F9FAFB;margin:0;'>
    Good day, <span style='background:linear-gradient(135deg,#00C9FF,#0066FF);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;'>{first_name}</span> 👋
  </h1>
  <p style='color:#6B7280;font-size:14px;margin:4px 0 0;'>
    Your health dashboard is active and monitoring in real-time.
  </p>
</div>""",
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs(["📡  Live Monitoring", "📋  Past Records", "🔬  Report Analysis"])

with tab1:
    bpm_placeholder, chart_placeholder = render_live_ui(email)

with tab2:
    render_records_tab(email)

with tab3:
    render_reports_tab(email)

run_live_polling(bpm_placeholder, chart_placeholder)
