"""
ui/styles.py — Global and Feature-Specific CSS Definitions
"""

from __future__ import annotations

import streamlit as st

GLOBAL_CSS: str = """
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
"""

SOS_CSS: str = """
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
"""


def apply_global_styles() -> None:
    """Inject global CSS rules into the Streamlit app."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def apply_sos_styles() -> None:
    """Inject SOS emergency button animation styles."""
    st.markdown(SOS_CSS, unsafe_allow_html=True)

