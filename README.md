## 🛡️ Safety Warning
*This tool is intended for triage and informational purposes only. It is not a replacement for professional medical diagnosis or hospital-grade ECG equipment.*

---

# 🩺 Intelli-Vitals: AI-Powered Touchless Health Monitoring

**Intelli-Vitals** is a comprehensive MedTech platform designed to provide equitable healthcare access. By leveraging Computer Vision and Large Language Models, it transforms any standard webcam into a clinical-grade vital sign monitor and diagnostic assistant.

## 🚀 Key Features

*   **Touchless Heart Rate Monitoring (rPPG):** Uses the **Plane-Orthogonal-to-Skin (POS)** algorithm to detect micro-variations in skin color, providing a real-time pulse wave.
*   **Clinical Lock with Gemini 1.5 Flash:** Eliminates "noise" by using Google Gemini to verify BPM readings against a 5-second signal window, ensuring medical-grade accuracy.
*   **Multimodal Diagnostic AI:** Simultaneously analyzes user facial markers and uploaded medical reports (PDF/JPG) to provide clinical snapshots and specialist recommendations.
*   **Obstruction & Liveness Guard:** Integrated **Mediapipe Face Mesh** stability checks to prevent false readings from environmental interference (e.g., transparent objects or movement).
*   **Smart SOS & Geolocation:** One-touch emergency response that fetches live coordinates and provides direct contact info for specialized hospitals in **Bhopal** (AIIMS, Hamidia, Bansal).
*   **Secure Patient History:** Google OAuth2 authentication paired with an SQLite backend to track and visualize health trends over time.

## 🛠️ Tech Stack

*   **Frontend:** [Streamlit](https://streamlit.io/)
*   **AI/ML:** [Google Gemini 1.5 Flash](https://aistudio.google.com/), [Mediapipe](https://google.github.io/mediapipe/)
*   **Vision & Signal Processing:** OpenCV, NumPy, SciPy (Butterworth Filters)
*   **Backend:** Python (FastAPI logic)
*   **Database:** SQLite3
*   **Auth:** Google OAuth2

## 📐 Technical Deep Dive: The POS Algorithm

Traditional rPPG often fails on darker skin tones due to melanin absorption. Intelli-Vitals implements the **POS (Plane-Orthogonal-to-Skin)** algorithm to ensure skin-tone neutrality. The signal is projected onto a plane orthogonal to the skin-tone direction:

$$P_x = G_n - B_n$$
$$P_y = G_n + B_n - 2R_n$$
$$S = P_x + \frac{\sigma(P_x)}{\sigma(P_y)} \cdot P_y$$

This mathematical projection isolates the Blood Volume Pulse (BVP) from background noise and skin pigmentation.

## 📦 Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/paliwalkartik/Hackdays--HealthTech-MedTech.git](https://github.com/paliwalkartik/Hackdays--HealthTech-MedTech.git)
    cd Hackdays--HealthTech-MedTech
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up Environment Variables:**
    Create a `.env` file and add your credentials:
    ```env
    GOOGLE_API_KEY=your_gemini_api_key
    GOOGLE_CLIENT_ID=your_oauth_client_id
    GOOGLE_CLIENT_SECRET=your_oauth_client_secret
    ```

4.  **Run the application:**
    ```bash
    streamlit run app.py
    ```

## 📂 Project Structure
```text
├── app.py              # Main Streamlit Dashboard
├── vitals_engine.py    # rPPG Signal Processing & POS Algorithm
├── consultant.py       # Gemini 1.5 Flash Multimodal Logic
├── health_data.db      # Local SQLite Database
├── requirements.txt    # Project Dependencies
└── services/           # SOS and Location Services
🛡️ Safety Warning
This tool is intended for triage and informational purposes only. It is not a replacement for professional medical diagnosis or hospital-grade ECG equipment.

Developed for the HealthTech & MedTech Hackathon 2026 | Bhopal, India
