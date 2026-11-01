"""
dashboard.py — Streamlit UI: Page Config, Wiring, and Tab Composition
"""

import html
import streamlit as st

from auth import handle_oauth_callback, init_session_state
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

# Authentication & Session Management
init_session_state()
handle_oauth_callback()
render_sidebar()

# Login Wall for unauthenticated users
if not st.session_state.get("connected"):
    render_login_wall()
    st.stop()

# Authenticated View
user_info = st.session_state.get("user_info", {})
email = user_info.get("email", "")
name = user_info.get("name", "User")
first_name = html.escape(name.split()[0] if name else "User")

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
    render_reports_tab()

run_live_polling(bpm_placeholder, chart_placeholder)
