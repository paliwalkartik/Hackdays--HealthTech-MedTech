# AGENTS.md — Intelli-Vitals

Standing context for any coding agent (Claude Code, Cursor, Windsurf) working in this repo.
Read this fully before every task. Then do exactly the prompt you were given, nothing more.

## What this project is
Touchless heart-rate monitoring from a webcam (rPPG, POS algorithm) + Gemini-based clinical snapshot + medical-report analysis + hospital suggestions + SOS. Built for the HealthTech & MedTech Hackathon 2026 (Bhopal, India). Target users: Indian patients with a phone/laptop camera.

**It is a wellness/triage aid, not a medical device.** Never write copy, comments, or UI text that claims diagnosis, "clinical-grade" or "medical-grade" accuracy, or that an action happened when it did not.

## Stack
Python 3.11 · FastAPI + uvicorn (`api.py`, port 8000) · Streamlit (`dashboard.py`, port 8501) · OpenCV · Mediapipe 0.10.14 (`mp.solutions`) · NumPy/SciPy · google-genai (Gemini) · SQLite (`health_data.db`) · Streamlit OIDC (Google OAuth).

## Files (current)
| File | Role |
|---|---|
| `config.py` | Central typed configuration (env + .env) |
| `api.py` | FastAPI: webcam capture thread, MJPEG `/video_feed`, `/vitals`, `/consult`, `/reset_vitals`, `/analyze_report` |
| `vitals_engine.py` | `VitalsEngine`: POS → band-pass → FFT BPM |
| `consultant.py` | `ClinicalConsultant`: Gemini snapshot from BPM list + face frame |
| `document_service.py` | `DocumentAnalysisService`: Gemini File API report analysis |
| `dashboard.py` | Streamlit entrypoint (page setup, wiring, tabs) |
| `auth.py` | Streamlit OIDC wrapper, profile sanitization, and Dev Mode bypass |
| `db.py` | Context-managed SQLite database interface for health records |
| `hospitals.py` | Hospital data loader and specialty lookup |
| `data/hospitals.json` | Hospital dataset for Bhopal medical centers |
| `ui/styles.py` | Global styling and SOS animation CSS |
| `ui/sidebar.py` | Sidebar navigation, login wall, and SOS emergency handling |
| `ui/live.py` | Tab 1: Live camera feed, vitals telemetry, and polling loop |
| `ui/records.py` | Tab 2: Patient health history and records table |
| `ui/reports.py` | Tab 3: Report upload analysis and hospital recommendation cards |
| `run.py` | Launches backend + dashboard |
| `requirements.txt` | Pinned production dependencies |
| `requirements-dev.txt` | Dev dependencies (`pytest`, `httpx`) |
| `tests/` | Synthetic unit and smoke test suite |

## Commands
```bash
pip install -r requirements.txt
python run.py                      # backend + dashboard
pytest -q                          # must stay green after every prompt
python -m py_compile *.py          # quick syntax check
```

## Hard rules
1. **Safety honesty.** UI/API text must never say an ambulance/doctor/hospital was contacted unless a real integration did it. Emergency actions are `tel:` links (India: 112 unified, 108 ambulance — verify before release).
2. **No secrets in code.** Keys, cookie secrets, OAuth credentials come from env / `.env` / `.streamlit/secrets.toml`. Never commit them. Never log them.
3. **Escape everything.** Any model output, filename, or user-provided string rendered with `unsafe_allow_html=True` must go through `html.escape`.
4. **The number in the DB is the measured number.** BPM and other metrics come from `VitalsEngine`, never from LLM output.
5. **LLM is the narrator, not the clinician.** Status/urgency thresholds are deterministic code; Gemini writes explanation text only, via structured JSON output, with a rule-based fallback if it fails.
6. **Privacy.** Face images and reports leave the device only after explicit in-app consent. Delete uploaded files from the Gemini File API after use. Never store raw face images.
7. **Thread safety.** All shared camera/vitals state goes through the lock introduced in BE-1.
8. **Don't break the demo.** Local single-user `python run.py` on Windows, macOS and Linux must keep working. Add features behind sensible defaults.
9. **Parameterised SQL only.** Use context-managed connections.
10. **Small, reviewable diffs.** One prompt = one logical change set. No drive-by reformatting or renames outside the prompt's scope.

## Conventions
- Python 3.11, type hints on new code, `logging` (not `print`) in new code, config via a single `config.py` (from CFG-1 onward).
- Tests live in `tests/`, use synthetic data only (no webcam, no network, no real Gemini calls — mock them).
- Pin dependencies; when adding one, add it to `requirements.txt` with a version.
- Medical thresholds and copy live in one module (`health_rules.py`, from AI-2 onward) so they can be reviewed by a clinician.

## Definition of done (every prompt)
- [ ] Code compiles, `pytest -q` passes, new behaviour has a test where feasible.
- [ ] `python run.py` still starts both services (if you cannot run a webcam, state which parts you could not verify).
- [ ] No new secrets, no new `unsafe_allow_html` without escaping.
- [ ] README / AGENTS.md updated if behaviour, env vars, or file layout changed.
- [ ] Final message lists: files changed, how you verified, anything you could not verify.

## Known limitations (do not "fix" silently)
- Accuracy of rPPG on real faces is unvalidated until the VAL prompts run.
- Hospital data is static and unverified until DATA-4 / UX-3 replace it.
- Server-side webcam means single-user local deployment until FEAT-5.

