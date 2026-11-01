## 🛡️ Safety Warning
*This tool is intended for wellness triage and informational purposes only. It is not a medical device, nor a replacement for professional clinical diagnosis or hospital-grade ECG equipment.*

---

# 🩺 Intelli-Vitals: AI-Powered Touchless Health Monitoring

**Intelli-Vitals** is a wellness triage aid built for the HealthTech & MedTech Hackathon 2026 (Bhopal, India). By leveraging Computer Vision and Large Language Models, it transforms a standard webcam into a non-invasive vital sign monitoring and diagnostic triage assistant.

## 🚀 Key Features

*   **Touchless Heart Rate Monitoring (rPPG):** Uses the **Plane-Orthogonal-to-Skin (POS)** algorithm to detect micro-variations in skin color, computing pulse rate from live webcam feed.
*   **Clinical Snapshot with Gemini:** Generates structured wellness observations from measured BPM telemetry and face frames.
*   **Multimodal Report Analysis:** Analyzes uploaded medical reports (PDF/JPG) using Gemini to explain lab findings and suggest relevant medical specialties.
*   **Face Tracking Guard:** Integrated **MediaPipe Face Mesh** stability checks to ensure reliable region-of-interest detection.
*   **Emergency SOS Assistance:** Direct access to emergency calling (`tel:112` / `tel:108` in India) and hospital directory for Bhopal medical centers (AIIMS, Hamidia, Bansal, Chirayu, etc.).
*   **Built-in Streamlit OIDC Authentication:** Seamless Google Sign-In with encrypted session tokens and user profile protection.

## 🛠️ Tech Stack

*   **Frontend:** [Streamlit](https://streamlit.io/) (`dashboard.py`, port 8501)
*   **Backend:** FastAPI + Uvicorn (`api.py`, port 8000)
*   **AI/ML:** Google Gemini (`google-genai`), MediaPipe
*   **Vision & Signal Processing:** OpenCV, NumPy, SciPy (Butterworth Filter & FFT)
*   **Database:** SQLite3 (`health_data.db`)
*   **Auth:** Streamlit Built-in OpenID Connect (OIDC) via Google OAuth 2.0 (`st.login`, `st.user`, `st.logout`)

---

## 🔒 Security Advisory: Secret Rotation

> [!WARNING]
> The legacy HMAC session secret key (`"intelli_vitals_2026_secret_hmac_key"`) was previously committed to this repository in historical revisions and must be treated as **publicly compromised and burned**.
> 
> The application has migrated entirely to Streamlit's built-in OIDC authentication. All session security now relies on a user-provided, random `cookie_secret` configured in `.streamlit/secrets.toml`. Never commit `.streamlit/secrets.toml` or `.env` to version control.

---

## 📦 Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/paliwalkartik/Hackdays--HealthTech-MedTech.git
cd Hackdays--HealthTech-MedTech
```

### 2. Create and activate a Python 3.11 virtual environment
```bash
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt   # Dev & test dependencies
```

### 4. Configure Environment (`.env`)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to set your Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

---

## 🔐 Google Cloud Console Setup (OIDC Authentication)

To enable Google Sign-In with Streamlit's built-in OIDC auth:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a Google Cloud project.
3. Configure the **OAuth consent screen** (User Type: External, Scopes: `openid`, `profile`, `email`).
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**.
5. Select Application type: **Web application**.
6. Set **Authorized redirect URIs**:
   ```
   http://localhost:8501/oauth2callback
   ```
   *(Note: The exact path `/oauth2callback` is required by Streamlit OIDC)*.
7. Click **Create** and copy your **Client ID** and **Client Secret**.

### Configure `.streamlit/secrets.toml`
Create `.streamlit/secrets.toml` (copy from `.streamlit/secrets.toml.example`):
```toml
# Gemini API Key (optional alternative to environment variable)
GEMINI_API_KEY = "your_gemini_api_key_here"

[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "generate-a-strong-random-secret-key-at-least-32-chars"
client_id = "your-client-id.apps.googleusercontent.com"
client_secret = "your-google-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

[auth.google]
client_id = "your-client-id.apps.googleusercontent.com"
client_secret = "your-google-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

---

## 🛠️ Local Development Mode (Offline Bypass)

If you are developing locally or testing offline without Google Cloud OAuth credentials, you can bypass authentication:

Set `IV_DEV_LOGIN=1` in your `.env` or shell:
```bash
# Windows PowerShell
$env:IV_DEV_LOGIN="1"

# Linux / macOS
export IV_DEV_LOGIN=1
```

When active, the dashboard displays a prominent yellow **DEV MODE ACTIVE** banner and allows one-click login into the dashboard with a mock developer profile.

---

## 🚀 Running the Application

Start both the FastAPI backend and Streamlit dashboard simultaneously:
```bash
python run.py
```
- **Backend API:** `http://127.0.0.1:8000` (health: `/health`, docs: `/docs`)
- **Streamlit UI:** `http://localhost:8501`
- **Inter-service Security:** `run.py` automatically generates a random per-process API token (`IV_API_TOKEN`) shared with both services via environment. All API endpoints except `/health` require authentication (`X-IV-Token` header or `?token=` parameter for video stream). Heavy endpoints (`/consult`, `/analyze_report`) are rate-limited to 6 requests/min per IP.

---

## 🧪 Testing
```bash
pytest -q
```
