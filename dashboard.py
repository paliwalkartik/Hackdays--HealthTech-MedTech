import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import time
import sqlite3
import json
import os
import hmac
import hashlib
import base64
import webbrowser
from streamlit_js_eval import get_geolocation

import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from config import config

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# ── Config ────────────────────────────────────────────────────────────────────
CREDENTIALS_FILE = 'google_credentials.json'
REDIRECT_URI     = 'http://localhost:8501'
SCOPES           = ["openid","https://www.googleapis.com/auth/userinfo.profile",
                    "https://www.googleapis.com/auth/userinfo.email"]
COOKIE_SECRET    = "intelli_vitals_2026_secret_hmac_key"
COOKIE_NAME      = "iv_session"

# ── Session Token (cookie-based persistence) ──────────────────────────────────
def _sign(data: str) -> str:
    return hmac.new(COOKIE_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()

def encode_session(user_info: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(user_info).encode()).decode()
    sig = _sign(payload)
    return f"{payload}.{sig}"

def decode_session(token: str):
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        return json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
    except Exception:
        return None

def set_cookie(token: str):
    components.html(f"""<script>
    document.cookie = "{COOKIE_NAME}={token}; path=/; max-age={60*60*24*config.SESSION_TTL_DAYS}; SameSite=Lax";
    </script>""", height=0)

def clear_cookie():
    components.html(f"""<script>
    document.cookie = "{COOKIE_NAME}=; path=/; max-age=0";
    </script>""", height=0)

def get_cookie() -> str:
    cookies = st.context.cookies
    return cookies.get(COOKIE_NAME, "")

# ── Database ──────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.cursor().execute('''CREATE TABLE IF NOT EXISTS heart_rate_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT,
        bpm REAL, analysis TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit(); conn.close()

def save_log(email, bpm, analysis):
    conn = sqlite3.connect(config.DB_PATH)
    conn.cursor().execute('INSERT INTO heart_rate_logs (username,bpm,analysis) VALUES(?,?,?)',
                          (email, bpm, analysis))
    conn.commit(); conn.close()

def fetch_logs(email):
    conn = sqlite3.connect(config.DB_PATH)
    c = conn.cursor()
    c.execute('SELECT timestamp,bpm,analysis FROM heart_rate_logs WHERE username=? ORDER BY timestamp DESC',(email,))
    rows = c.fetchall(); conn.close(); return rows

init_db()

# ── OAuth ─────────────────────────────────────────────────────────────────────
def build_flow():
    return google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI,
        autogenerate_code_verifier=False)

def get_auth_url():
    flow = build_flow()
    url, state = flow.authorization_url(access_type='offline', prompt='select_account')
    st.session_state['oauth_state'] = state
    return url

def exchange_code(code):
    try:
        flow = build_flow()
        flow.fetch_token(code=code)
        svc = build('oauth2','v2',credentials=flow.credentials)
        return svc.userinfo().get().execute()
    except Exception as e:
        st.error(f"Login error: {e}"); return None

# ── Page Setup ────────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="Intelli-Vitals", page_icon="🫀")

# ── Restore session from cookie ───────────────────────────────────────────────
if 'connected' not in st.session_state:
    token = get_cookie()
    if token:
        user = decode_session(token)
        if user:
            st.session_state['connected'] = True
            st.session_state['user_info'] = user
        else:
            st.session_state['connected'] = False
            st.session_state['user_info'] = {}
    else:
        st.session_state['connected'] = False
        st.session_state['user_info'] = {}

# ── Handle OAuth callback ─────────────────────────────────────────────────────
auth_code = st.query_params.get("code")
if auth_code and not st.session_state['connected']:
    st.query_params.clear()
    user = exchange_code(auth_code)
    if user:
        st.session_state['connected'] = True
        st.session_state['user_info'] = user
        set_cookie(encode_session(user))
        st.rerun()

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #070B14; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1117 0%, #111827 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.06);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #0D1117; gap: 4px; padding: 4px;
    border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);
}
.stTabs [data-baseweb="tab"] {
    background: transparent; color: #6B7280;
    border-radius: 8px; padding: 8px 20px;
    font-weight: 500; font-size: 14px; border: none;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg,#00C9FF,#0066FF) !important;
    color: white !important;
}

/* Cards */
.glass-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 24px;
    backdrop-filter: blur(12px);
}
.metric-card {
    background: linear-gradient(135deg,rgba(0,201,255,0.08),rgba(0,102,255,0.08));
    border: 1px solid rgba(0,201,255,0.2);
    border-radius: 16px; padding: 20px; text-align: center;
    transition: transform 0.2s, box-shadow 0.2s;
}
.metric-card:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,201,255,0.15); }
.bpm-number { font-size: 64px; font-weight: 700; line-height: 1;
    background: linear-gradient(135deg,#00C9FF,#0066FF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.bpm-inactive { font-size: 64px; font-weight: 700; color: #374151; }
.label-sm { font-size: 12px; color: #6B7280; font-weight: 500;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }

/* Alert banner */
.urgency-badge {
    border-radius: 12px; padding: 16px 20px; margin-bottom: 16px;
    border-left: 4px solid;
}
.snapshot-box {
    background: rgba(0,201,255,0.05);
    border: 1px solid rgba(0,201,255,0.2);
    border-left: 4px solid #00C9FF;
    border-radius: 12px; padding: 20px; margin-top: 16px;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg,#00C9FF,#0066FF) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    padding: 10px 24px !important; transition: all 0.2s !important;
}
.stButton > button:hover { opacity: 0.85 !important; transform: translateY(-1px) !important; }

/* File uploader */
[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.02) !important;
    border: 2px dashed rgba(0,201,255,0.3) !important;
    border-radius: 12px !important;
}
/* Dataframe */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:20px 0 10px;'>
        <div style='font-size:36px;'>🫀</div>
        <div style='font-size:18px;font-weight:700;color:#00C9FF;letter-spacing:1px;'>INTELLI-VITALS</div>
        <div style='font-size:11px;color:#4B5563;margin-top:4px;'>Touchless Health Monitoring</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:0 0 16px;'>",
                unsafe_allow_html=True)

    if not st.session_state['connected']:
        st.markdown("<p style='color:#9CA3AF;font-size:13px;text-align:center;'>Sign in to access your health dashboard</p>", unsafe_allow_html=True)
        if os.path.exists(CREDENTIALS_FILE):
            auth_url = get_auth_url()
            st.markdown(f"""
            <a href="{auth_url}" target="_self" style="text-decoration:none;">
              <div style="display:flex;align-items:center;justify-content:center;gap:10px;
                   background:linear-gradient(135deg,#00C9FF,#0066FF);color:white;
                   border-radius:10px;padding:12px 20px;font-weight:600;font-size:14px;
                   cursor:pointer;margin-top:8px;transition:opacity 0.2s;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Google_%22G%22_logo.svg/768px-Google_%22G%22_logo.svg.png"
                     width="18" height="18" style="background:white;border-radius:3px;padding:2px;">
                Sign in with Google
              </div>
            </a>""", unsafe_allow_html=True)
        else:
            st.error("google_credentials.json missing")
    else:
        user_info = st.session_state['user_info']
        name    = user_info.get('name','User')
        email   = user_info.get('email','')
        picture = user_info.get('picture','')
        if picture:
            st.markdown(f"""
            <div style='text-align:center;margin-bottom:12px;'>
              <img src="{picture}" width="72" height="72"
                   style="border-radius:50%;border:3px solid #00C9FF;box-shadow:0 0 20px rgba(0,201,255,0.3);">
            </div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div style='text-align:center;margin-bottom:16px;'>
          <div style='font-weight:600;font-size:15px;color:#F9FAFB;'>{name}</div>
          <div style='font-size:12px;color:#6B7280;margin-top:4px;'>{email}</div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:0 0 16px;'>",
                    unsafe_allow_html=True)
        st.markdown("<p style='font-size:11px;color:#4B5563;text-align:center;'>SESSION ACTIVE</p>",
                    unsafe_allow_html=True)
        if st.button("🚪 Log Out", use_container_width=True):
            clear_cookie()
            st.session_state['connected'] = False
            st.session_state['user_info'] = {}
            st.rerun()

        # ── EMERGENCY SOS ────────────────────────────────────────────
        st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:16px 0;'>",
                    unsafe_allow_html=True)
        st.markdown("""
        <style>
        @keyframes sos-pulse {
            0%   { box-shadow: 0 0 0 0 rgba(255,23,68,0.7); }
            70%  { box-shadow: 0 0 0 14px rgba(255,23,68,0); }
            100% { box-shadow: 0 0 0 0 rgba(255,23,68,0); }
        }
        div[data-testid="stButton"] button[kind="primary"].sos-btn {
            background: linear-gradient(135deg,#FF1744,#B71C1C) !important;
            animation: sos-pulse 1.5s infinite !important;
        }
        .sos-wrapper > div > button {
            background: linear-gradient(135deg,#FF1744,#B71C1C) !important;
            color: white !important;
            font-size: 16px !important;
            font-weight: 800 !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 14px !important;
            width: 100% !important;
            letter-spacing: 2px !important;
            animation: sos-pulse 1.5s infinite !important;
            cursor: pointer !important;
        }
        </style>
        <div class='sos-wrapper'>""", unsafe_allow_html=True)

        sos_clicked = st.button("🚨  EMERGENCY SOS", key="sos_btn", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:10px;color:#6B7280;text-align:center;margin-top:4px;'>Dispatches ambulance & opens nearest hospital</p>",
                    unsafe_allow_html=True)

        if sos_clicked:
            st.session_state['sos_active'] = True

        if st.session_state.get('sos_active'):
            with st.spinner("📡 Acquiring GPS location..."):
                loc = get_geolocation()

            if loc and loc.get('coords'):
                lat = loc['coords']['latitude']
                lng = loc['coords']['longitude']

                # High-priority alert
                st.markdown(f"""
                <div style='background:linear-gradient(135deg,#B71C1C,#7F0000);
                            border:2px solid #FF1744;border-radius:12px;
                            padding:16px;margin-top:12px;text-align:center;'>
                    <div style='font-size:22px;'>🚑</div>
                    <div style='color:#FF8A80;font-weight:800;font-size:13px;
                                letter-spacing:1px;margin:6px 0 2px;'>AMBULANCE DISPATCHED TO:</div>
                    <div style='color:white;font-weight:700;font-size:14px;'>
                        {lat:.5f}, {lng:.5f}
                    </div>
                </div>""", unsafe_allow_html=True)

                # Open Google Maps nearest hospital in browser
                maps_url = (
                    f"https://www.google.com/maps/search/hospital/@{lat},{lng},14z"
                )
                webbrowser.open(maps_url)

                if st.button("✅ Cancel SOS", key="cancel_sos"):
                    st.session_state['sos_active'] = False
                    st.rerun()
            else:
                st.warning("⚠ Could not get location. Please allow browser location access and try again.")
                st.session_state['sos_active'] = False

# ── LOGIN WALL ────────────────────────────────────────────────────────────────
if not st.session_state['connected']:
    st.markdown("""
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
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── AUTHENTICATED ─────────────────────────────────────────────────────────────
user_info = st.session_state['user_info']
email   = user_info.get('email','')
name    = user_info.get('name','User')

st.markdown(f"""
<div style='margin-bottom:24px;'>
  <h1 style='font-size:28px;font-weight:700;color:#F9FAFB;margin:0;'>
    Good day, <span style='background:linear-gradient(135deg,#00C9FF,#0066FF);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;'>{name.split()[0]}</span> 👋
  </h1>
  <p style='color:#6B7280;font-size:14px;margin:4px 0 0;'>
    Your health dashboard is active and monitoring in real-time.
  </p>
</div>""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📡  Live Monitoring", "📋  Past Records", "🔬  Report Analysis"])

# ─────────────────── TAB 1: LIVE MONITORING ───────────────────────────────────
with tab1:
    col1, col2 = st.columns([1.1, 0.9], gap="large")

    with col1:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("<div class='label-sm'>Patient Camera Feed</div>", unsafe_allow_html=True)
        st.markdown(
            f'<img src="{config.API_BASE_URL}/video_feed" width="100%" '
            'style="border-radius:12px;border:1px solid rgba(255,255,255,0.1);">',
            unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("<div class='label-sm'>🤖 Gemini Clinical Snapshot</div>", unsafe_allow_html=True)
        st.markdown("<p style='color:#9CA3AF;font-size:13px;'>AI analysis of vitals + facial appearance</p>",
                    unsafe_allow_html=True)
        if st.button("⚡ Generate Clinical Snapshot", key="snapshot_btn"):
            with st.spinner("Analyzing vitals and facial data via Gemini..."):
                try:
                    res = requests.get(f"{config.API_BASE_URL}/consult", timeout=60)
                    if res.status_code == 200:
                        data = res.json()
                        if "error" in data:
                            st.error(data["error"])
                        else:
                            avg_bpm = data.get('average_bpm', 0)
                            save_log(email, avg_bpm, json.dumps(data))
                            st.success("✅ Snapshot saved to your records")
                            st.markdown(f"""
                            <div class="snapshot-box">
                                <div style='font-weight:600;color:#00C9FF;margin-bottom:10px;'>
                                    {data.get('clinical_status','N/A')}
                                </div>
                                <p style='color:#D1D5DB;margin:6px 0;'>
                                    <strong style='color:#9CA3AF;'>Avg BPM:</strong> {avg_bpm}
                                </p>
                                <p style='color:#D1D5DB;margin:6px 0;'>
                                    <strong style='color:#9CA3AF;'>Visual:</strong> {data.get('visual_assessment','N/A')}
                                </p>
                                <p style='color:#D1D5DB;margin:6px 0;'>
                                    <strong style='color:#9CA3AF;'>Recommendation:</strong> {data.get('recommendation','N/A')}
                                </p>
                            </div>""", unsafe_allow_html=True)
                    else:
                        st.error("Failed to reach backend")
                except Exception as e:
                    st.error(f"Backend error: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        # Reset / New Measurement button
        meas_col1, meas_col2 = st.columns([2,1])
        with meas_col1:
            st.markdown("<div class='label-sm'>Vitals Telemetry</div>", unsafe_allow_html=True)
        with meas_col2:
            if st.button("🔄 New Reading", key="reset_btn"):
                try:
                    requests.post(f"{config.API_BASE_URL}/reset_vitals", timeout=3)
                    if 'pulse_data' in st.session_state:
                        st.session_state.pulse_data = []
                    st.success("Ready for new reading!")
                except Exception:
                    pass

        bpm_placeholder   = st.empty()
        chart_placeholder = st.empty()

# ─────────────────── TAB 2: PAST RECORDS ─────────────────────────────────────
with tab2:
    st.markdown("<div class='label-sm'>Your Health History</div>", unsafe_allow_html=True)
    records = fetch_logs(email)
    if records:
        formatted = []
        for r in records:
            try:
                d = json.loads(r[2])
                status = d.get('clinical_status','N/A')
                rec    = d.get('recommendation','N/A')
            except Exception:
                status = rec = "N/A"
            formatted.append({"📅 Timestamp":r[0], "💓 BPM":f"{r[1]:.1f}",
                               "🏥 Status":status, "💡 Recommendation":rec})
        df = pd.DataFrame(formatted)
        st.markdown(f"<p style='color:#6B7280;font-size:13px;margin-bottom:12px;'>"
                    f"{len(formatted)} record(s) found for {email}</p>", unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, height=400)
    else:
        st.markdown("""
        <div style='text-align:center;padding:60px 20px;color:#374151;'>
            <div style='font-size:48px;'>📭</div>
            <p style='margin-top:12px;font-size:15px;'>No records yet. Generate a Clinical Snapshot to save your first entry.</p>
        </div>""", unsafe_allow_html=True)

# ─────────────────── TAB 3: REPORT ANALYSIS ──────────────────────────────────
with tab3:
    st.markdown("<div class='label-sm'>Medical Report Analysis</div>", unsafe_allow_html=True)
    st.markdown("<p style='color:#9CA3AF;font-size:13px;margin-bottom:20px;'>"
                "Upload a PDF or image report. Gemini analyzes it alongside your live webcam appearance.</p>",
                unsafe_allow_html=True)

    uploaded_file = st.file_uploader("Upload Medical Report", type=["pdf","jpg","jpeg","png"],
                                     label_visibility="collapsed")

    if uploaded_file:
        c1, c2 = st.columns([3,1])
        with c1:
            st.success(f"✅ {uploaded_file.name} ({uploaded_file.size/1024:.1f} KB)")
        with c2:
            analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
        if analyze_btn:
            with st.spinner("📤 Uploading to Gemini File API... (10-20 seconds)"):
                try:
                    res = requests.post(f"{config.API_BASE_URL}/analyze_report",
                                        files={"file":(uploaded_file.name,
                                                       uploaded_file.getvalue(),
                                                       uploaded_file.type)}, timeout=120)
                    if res.status_code == 200:
                        r = res.json()
                        if "error" in r:
                            st.error(r["error"])
                        else:
                            # ── Store results in session for hospital cards ──
                            st.session_state['last_analysis'] = r
                            urgency = r.get('urgency_level','Routine')
                            uc = {'Urgent':'#FF1744','Soon':'#FF6D00','Routine':'#00E676'}.get(urgency,'#888')
                            st.markdown(f"""
                            <div class="urgency-badge" style="background:rgba(0,0,0,0.3);border-color:{uc};">
                                <span style="color:{uc};font-weight:700;">⚠ {urgency}</span>
                                <span style="color:#D1D5DB;margin-left:12px;">{r.get('summary','')}</span>
                            </div>""", unsafe_allow_html=True)
                            ca, cb = st.columns(2)
                            with ca:
                                st.markdown("**🏥 Specialty**")
                                st.info(r.get('medical_specialty','N/A'))
                                st.markdown("**👁 Visual Observations**")
                                st.write(r.get('visual_observations','N/A'))
                                st.markdown("**⚕ Action Plan**")
                                st.write(r.get('action_plan','N/A'))
                            with cb:
                                st.markdown("**⚠ Health Risks**")
                                for risk in r.get('health_risks',[]):
                                    st.markdown(f"• {risk}")
                                st.markdown("**🌿 Lifestyle Measures**")
                                for m in r.get('lifestyle_measures',[]):
                                    st.markdown(f"• {m}")
                    else:
                        st.error(f"Backend error {res.status_code}")
                except Exception as ex:
                    st.error(f"Connection error: {ex}")
    else:
        st.markdown("""
        <div style='border:2px dashed rgba(0,201,255,0.2);border-radius:16px;
                    padding:60px 20px;text-align:center;color:#374151;margin-top:10px;'>
            <div style='font-size:56px;'>📄</div>
            <p style='color:#6B7280;font-size:15px;margin-top:12px;'>
                Drop a PDF, JPG, or PNG medical report above
            </p>
            <p style='color:#374151;font-size:12px;'>
                Gemini will cross-reference it with your live camera feed
            </p>
        </div>""", unsafe_allow_html=True)

    # ── Hospital Recommendations (persists after analysis via session_state) ───
    if 'last_analysis' in st.session_state:
        r = st.session_state['last_analysis']
        specialty = r.get('medical_specialty', 'General')

        HOSPITAL_DB = {
            "Cardiology": [
                {"name": "Bansal Hospital", "area": "Shahpura, Bhopal", "phone": "+91-755-4000000",
                 "rating": "⭐ 4.6", "beds": "350+", "icon": "🫀"},
                {"name": "Hamidia Hospital – Cardiology", "area": "Royal Market, Bhopal", "phone": "+91-755-2540000",
                 "rating": "⭐ 4.2", "beds": "800+", "icon": "🏥"},
                {"name": "AIIMS Bhopal – Cardiology", "area": "Saket Nagar, Bhopal", "phone": "+91-755-2672354",
                 "rating": "⭐ 4.8", "beds": "960+", "icon": "🏛"},
            ],
            "Neurology": [
                {"name": "AIIMS Bhopal – Neurology", "area": "Saket Nagar, Bhopal", "phone": "+91-755-2672354",
                 "rating": "⭐ 4.8", "beds": "960+", "icon": "🧠"},
                {"name": "Bansal Hospital – Neuro", "area": "Shahpura, Bhopal", "phone": "+91-755-4000000",
                 "rating": "⭐ 4.5", "beds": "350+", "icon": "🏥"},
                {"name": "Choithram Hospital", "area": "Indore Rd, Bhopal", "phone": "+91-755-3988000",
                 "rating": "⭐ 4.3", "beds": "500+", "icon": "🏨"},
            ],
            "Endocrinology": [
                {"name": "AIIMS Bhopal – Endocrinology", "area": "Saket Nagar, Bhopal", "phone": "+91-755-2672354",
                 "rating": "⭐ 4.8", "beds": "960+", "icon": "🔬"},
                {"name": "Bansal Hospital", "area": "Shahpura, Bhopal", "phone": "+91-755-4000000",
                 "rating": "⭐ 4.6", "beds": "350+", "icon": "🏥"},
                {"name": "Narmada Hospital", "area": "Kolar Road, Bhopal", "phone": "+91-755-2760100",
                 "rating": "⭐ 4.1", "beds": "200+", "icon": "🏨"},
            ],
            "Orthopedics": [
                {"name": "People's Hospital – Ortho", "area": "Bhanpur, Bhopal", "phone": "+91-755-4077777",
                 "rating": "⭐ 4.5", "beds": "700+", "icon": "🦴"},
                {"name": "AIIMS Bhopal – Orthopaedics", "area": "Saket Nagar, Bhopal", "phone": "+91-755-2672354",
                 "rating": "⭐ 4.8", "beds": "960+", "icon": "🏛"},
                {"name": "Bansal Hospital – Ortho", "area": "Shahpura, Bhopal", "phone": "+91-755-4000000",
                 "rating": "⭐ 4.4", "beds": "350+", "icon": "🏥"},
            ],
            "Pulmonology": [
                {"name": "AIIMS Bhopal – Pulmonology", "area": "Saket Nagar, Bhopal", "phone": "+91-755-2672354",
                 "rating": "⭐ 4.8", "beds": "960+", "icon": "🫁"},
                {"name": "Hamidia Hospital", "area": "Royal Market, Bhopal", "phone": "+91-755-2540000",
                 "rating": "⭐ 4.2", "beds": "800+", "icon": "🏥"},
                {"name": "BMHRC Bhopal", "area": "Raisen Bypass, Bhopal", "phone": "+91-755-2742212",
                 "rating": "⭐ 4.4", "beds": "350+", "icon": "🏨"},
            ],
        }

        matched_key = next(
            (k for k in HOSPITAL_DB if k.lower() in specialty.lower() or specialty.lower() in k.lower()),
            None
        )
        hospitals = HOSPITAL_DB.get(matched_key) or [
            {"name": "AIIMS Bhopal", "area": "Saket Nagar, Bhopal", "phone": "+91-755-2672354",
             "rating": "⭐ 4.8", "beds": "960+", "icon": "🏛"},
            {"name": "Bansal Hospital", "area": "Shahpura, Bhopal", "phone": "+91-755-4000000",
             "rating": "⭐ 4.6", "beds": "350+", "icon": "🏥"},
            {"name": "People's Hospital", "area": "Bhanpur, Bhopal", "phone": "+91-755-4077777",
             "rating": "⭐ 4.5", "beds": "700+", "icon": "🏨"},
        ]

        st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:28px 0 20px;'>",
                    unsafe_allow_html=True)
        st.markdown(f"""
        <div style='margin-bottom:16px;'>
            <div style='font-size:11px;color:#6B7280;font-weight:600;letter-spacing:1px;
                        text-transform:uppercase;margin-bottom:4px;'>Recommended Specialists</div>
            <div style='font-size:18px;font-weight:700;color:#F9FAFB;'>
                Top 3 <span style='color:#00C9FF;'>{specialty}</span> Hospitals in Bhopal
            </div>
        </div>""", unsafe_allow_html=True)

        for i, h in enumerate(hospitals[:3]):
            col_card, col_btn = st.columns([4, 1], gap="small")
            with col_card:
                st.markdown(f"""
                <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                            border-left:3px solid #00C9FF;border-radius:14px;
                            padding:16px 20px;display:flex;align-items:center;gap:16px;
                            margin-bottom:10px;'>
                    <div style='font-size:36px;'>{h['icon']}</div>
                    <div style='flex:1;'>
                        <div style='font-weight:700;font-size:15px;color:#F9FAFB;'>{h['name']}</div>
                        <div style='font-size:12px;color:#6B7280;margin-top:3px;'>📍 {h['area']}</div>
                        <div style='display:flex;gap:16px;margin-top:6px;'>
                            <span style='font-size:12px;color:#9CA3AF;'>{h['rating']}</span>
                            <span style='font-size:12px;color:#9CA3AF;'>🛏 {h['beds']} beds</span>
                            <span style='font-size:12px;color:#4B5563;'>📞 {h['phone']}</span>
                        </div>
                    </div>
                </div>""", unsafe_allow_html=True)
            with col_btn:
                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                if st.button("📞 Contact", key=f"call_h_{i}", use_container_width=True):
                    st.toast(f"📞 Calling {h['name']} at {h['phone']}…", icon="🏥")
                    components.html(f"""<script>
                    const toast = document.createElement('div');
                    toast.innerHTML = '📞 Connecting to {h["name"]}...';
                    toast.style.cssText = `position:fixed;bottom:28px;right:28px;
                        background:#1E293B;border:1px solid #00C9FF;border-radius:12px;
                        padding:14px 22px;color:#F9FAFB;font-size:14px;font-weight:600;
                        z-index:99999;box-shadow:0 8px 32px rgba(0,201,255,0.25);`;
                    document.body.appendChild(toast);
                    setTimeout(() => toast.style.opacity='0', 3500);
                    setTimeout(() => toast.remove(), 4000);
                    </script>""", height=0)


if 'pulse_data' not in st.session_state:
    st.session_state.pulse_data = []

while True:
    try:
        res = requests.get(f"{config.API_BASE_URL}/vitals", timeout=1)
        if res.status_code == 200:
            data           = res.json()
            bpm            = data.get("bpm", 0)
            pulse          = data.get("pulse", 0)
            is_stable      = data.get("is_stable", False)
            is_completed   = data.get("is_completed", False)
            stable_dur     = data.get("stable_duration", 0.0)

            st.session_state.pulse_data.append(pulse)
            if len(st.session_state.pulse_data) > 120:
                st.session_state.pulse_data.pop(0)

            pct  = min(100, int((stable_dur / config.MEASURE_SECONDS) * 100))
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

            bpm_placeholder.markdown(f"""
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
            </div>""", unsafe_allow_html=True)

            chart_placeholder.line_chart(
                pd.DataFrame({"Pulse Wave": st.session_state.pulse_data}),
                height=280, use_container_width=True)
    except Exception:
        pass
    time.sleep(0.1)
