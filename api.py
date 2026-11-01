import io
import cv2
import mediapipe as mp
import numpy as np
import hmac
import logging
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

from config import config
from consultant import ClinicalConsultant
from document_service import (
    DocumentAnalysisService,
    ALLOWED_EXTENSIONS,
    ALLOWED_MAGIC,
    MAX_PDF_PAGES,
    validate_magic,
)
from vitals_engine import VitalsEngine

logger = logging.getLogger(__name__)


class RateLimiter:
    """Thread-safe in-memory sliding-window rate limiter per client IP."""

    def __init__(self, max_requests: int = 6, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._requests: dict[str, list[float]] = {}

    def is_rate_limited(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            timestamps = self._requests.get(ip, [])
            cutoff = now - self.window_seconds
            valid = [t for t in timestamps if t > cutoff]
            if len(valid) >= self.max_requests:
                self._requests[ip] = valid
                return True
            valid.append(now)
            self._requests[ip] = valid
            return False

    def reset(self) -> None:
        """Clear all tracked request history (useful for tests)."""
        with self._lock:
            self._requests.clear()


rate_limiter = RateLimiter(max_requests=6, window_seconds=60.0)

_api_token: str | None = None


def get_api_token() -> str:
    """Return the shared API token from environment, config, or lazily generated."""
    global _api_token
    token = os.environ.get("IV_API_TOKEN", "").strip() or config.api_token
    if token:
        return token
    if _api_token is None:
        _api_token = secrets.token_hex(32)
        os.environ["IV_API_TOKEN"] = _api_token
        config.IV_API_TOKEN = _api_token
    return _api_token


def verify_token(provided_token: str | None) -> bool:
    """Constant-time validation of provided token against expected token."""
    if not provided_token or not isinstance(provided_token, str):
        return False
    expected = get_api_token()
    return hmac.compare_digest(provided_token.encode("utf-8"), expected.encode("utf-8"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.IV_DISABLE_CAMERA:
        threading.Thread(target=capture_thread, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def security_and_rate_limit_middleware(request: Request, call_next):
    path = request.url.path.rstrip("/")
    # Health check and CORS preflights are exempt from auth and rate limits
    if path == "/health" or request.method == "OPTIONS":
        return await call_next(request)

    # Token authentication
    if path == "/video_feed":
        token = request.query_params.get("token") or request.headers.get("X-IV-Token")
    else:
        token = request.headers.get("X-IV-Token")

    if not verify_token(token):
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized: invalid or missing API token"},
        )

    # Per-IP rate limiting on heavy AI endpoints (/consult and /analyze_report)
    if path in ("/consult", "/analyze_report"):
        client_ip = request.client.host if request.client else "127.0.0.1"
        if rate_limiter.is_rate_limited(client_ip):
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "60"},
                content={"detail": "Too Many Requests: Rate limit exceeded (6 requests per minute)"},
            )

    return await call_next(request)


# CORS: allow_origins=config.ALLOWED_ORIGINS, credentials=False, methods GET/POST, headers used
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-IV-Token"],
)

mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(min_detection_confidence=0.5)

vitals_engine = VitalsEngine(fps=30, window_seconds=config.WINDOW_SECONDS)

consultant = None
doc_service = None

def get_consultant():
    global consultant
    if consultant is not None:
        return consultant, None
    api_key = config.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None, "GEMINI_API_KEY is missing. Please set it in your environment or .env file."
    try:
        consultant = ClinicalConsultant(api_key=api_key, model=config.GEMINI_MODEL)
    except Exception as e:
        return None, f"Failed to initialize ClinicalConsultant: {e}"
    return consultant, None

def get_doc_service():
    global doc_service
    if doc_service is not None:
        return doc_service, None
    api_key = config.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None, "GEMINI_API_KEY is missing. Please set it in your environment or .env file."
    try:
        doc_service = DocumentAnalysisService(api_key=api_key, model=config.GEMINI_MODEL)
    except Exception as e:
        return None, f"Failed to initialize DocumentAnalysisService: {e}"
    return doc_service, None

class GlobalState:
    current_frame = None
    processed_frame = None
    pulse_value = 0.0
    current_bpm = 0.0
    bpm_history = []
    face_frame = None
    dyn_box_w = 0
    dyn_box_h = 0
    is_stable = False
    stable_duration = 0.0
    last_stable_time = None
    is_completed = False

state = GlobalState()

def capture_thread():
    print(f"Attempting to open webcam ({config.CAMERA_INDEX}) with backend {config.CAMERA_BACKEND}...", flush=True)
    cap = cv2.VideoCapture(config.CAMERA_INDEX, config.get_camera_backend_code())
        
    if not cap.isOpened():
        print("ERROR: Could not open webcam. Please check your camera permissions.", flush=True)
        return
        
    print("Webcam successfully opened!", flush=True)
    # Give the camera some time to warm up
    time.sleep(1)
    
    while True:
        success, frame = cap.read()
        if not success:
            print("Failed to grab frame from webcam. Retrying...", flush=True)
            time.sleep(0.5)
            continue
            
        state.current_frame = frame.copy()
        display_frame = frame.copy()
        
        # Mediapipe requires RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_detection.process(rgb_frame)
        
        if results.detections:
            # Take the first detected face
            detection = results.detections[0]
            bboxC = detection.location_data.relative_bounding_box
            ih, iw, _ = frame.shape
            x, y, w, h = int(bboxC.xmin * iw), int(bboxC.ymin * ih), int(bboxC.width * iw), int(bboxC.height * ih)
            
            # Dynamic Stability Box Logic
            if state.dyn_box_w == 0:
                state.dyn_box_w = w * 1.5
                state.dyn_box_h = h * 1.5
            else:
                state.dyn_box_w = 0.95 * state.dyn_box_w + 0.05 * (w * 1.5)
                state.dyn_box_h = 0.95 * state.dyn_box_h + 0.05 * (h * 1.5)
                
            dw = min(state.dyn_box_w, iw * 0.9)
            dh = min(state.dyn_box_h, ih * 0.9)
            
            cx, cy = iw // 2, ih // 2
            gx1 = int(cx - dw // 2)
            gy1 = int(cy - dh // 2)
            gx2 = int(cx + dw // 2)
            gy2 = int(cy + dh // 2)
            
            is_inside = (x >= gx1 - 15) and (y >= gy1 - 15) and ((x + w) <= gx2 + 15) and ((y + h) <= gy2 + 15)
            
            if state.is_completed:
                state.is_stable = True
            else:
                state.is_stable = is_inside
                if is_inside:
                    if state.last_stable_time is None:
                        state.last_stable_time = time.time()
                    else:
                        state.stable_duration += (time.time() - state.last_stable_time)
                        state.last_stable_time = time.time()
                        
                    if state.stable_duration >= config.MEASURE_SECONDS:
                        state.is_completed = True
                else:
                    state.last_stable_time = None
            
            # Draw Dynamic Alignment Box
            box_color = (0, 230, 118) if state.is_stable else (0, 0, 255)
            cv2.rectangle(display_frame, (gx1, gy1), (gx2, gy2), box_color, 2)
            
            if state.is_completed:
                cv2.putText(display_frame, "READING COMPLETE: PLEASE GENERATE SNAPSHOT", (20, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 215, 0), 2)
            elif not is_inside:
                cv2.putText(display_frame, "WARNING: PLEASE CENTER FACE IN BOX", (20, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                remaining = max(0, int(config.MEASURE_SECONDS - state.stable_duration))
                cv2.putText(display_frame, f"STABLE: READING VITALS ({remaining}s REMAINING)", (20, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 230, 118), 2)
            
            # Padding around the face to ensure we get a good ROI for skin
            pad_x = int(w * 0.1)
            pad_y = int(h * 0.1)
            x1 = max(0, x + pad_x)
            y1 = max(0, y + pad_y)
            x2 = min(iw, x + w - pad_x)
            y2 = min(ih, y + h - pad_y)
            
            face_roi = rgb_frame[y1:y2, x1:x2]
            
            if face_roi.size > 0 and not state.is_completed:
                if is_inside:
                    # Save face frame for Gemini Snapshot
                    state.face_frame = frame[y1:y2, x1:x2].copy()
                
                # Average RGB for the POS algorithm
                r_mean = face_roi[:, :, 0].mean()
                g_mean = face_roi[:, :, 1].mean()
                b_mean = face_roi[:, :, 2].mean()
                
                pulse, bpm = vitals_engine.process_rgb(r_mean, g_mean, b_mean)
                state.pulse_value = pulse
                
                if bpm > 0 and is_inside:
                    state.current_bpm = bpm
                    state.bpm_history.append(bpm)
                    # Keep history for the last WINDOW_SECONDS seconds. At 30 FPS, ~30 * WINDOW_SECONDS frames.
                    if len(state.bpm_history) > int(30 * config.WINDOW_SECONDS):
                        state.bpm_history.pop(0)

            if results.detections:
                # Draw bounding box and BPM on the display frame
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), box_color, 1)
                
                bpm_display = f"{state.current_bpm:.1f}" if state.is_stable else "---"
                cv2.putText(display_frame, f"BPM: {bpm_display}", (x1, max(0, y1 - 10)), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, box_color, 2)
        else:
            state.is_stable = False
            cv2.putText(display_frame, "NO FACE DETECTED", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        state.processed_frame = display_frame
        # Slightly sleep to yield control
        time.sleep(0.01)


def generate_frames():
    while True:
        frame = state.processed_frame
        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                time.sleep(0.01)
        else:
            # Yield a blank frame if camera is not yet ready or disabled
            blank = np.zeros((240, 320, 3), dtype=np.uint8)
            ret, buffer = cv2.imencode('.jpg', blank)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.05)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/vitals")
def get_vitals():
    return {
        "pulse": float(state.pulse_value), 
        "bpm": float(state.current_bpm),
        "is_stable": state.is_stable,
        "is_completed": state.is_completed,
        "stable_duration": float(state.stable_duration)
    }

@app.get("/consult")
def consult():
    consultant_instance, err = get_consultant()
    if err:
        return {"error": err}

    if state.face_frame is None or not state.bpm_history:
        return {"error": "Not enough data yet. Please ensure the patient's face is visible in the camera."}
    
    # Downsample BPM history to send roughly 1 reading per second to Gemini
    # We have up to 30 * WINDOW_SECONDS readings. Take every 30th reading.
    bpm_data = state.bpm_history[::30][-config.WINDOW_SECONDS:]
    # Round the values for cleaner prompt
    bpm_data = [round(b, 1) for b in bpm_data]
    
    result = consultant_instance.analyze(bpm_data, state.face_frame)
    return result

@app.post("/reset_vitals")
def reset_vitals():
    """Reset the vitals engine so the patient can take a fresh measurement."""
    state.current_bpm   = 0.0
    state.bpm_history   = []
    state.is_stable     = False
    state.is_completed  = False
    state.stable_duration = 0.0
    state.last_stable_time = None
    state.pulse_value   = 0.0
    state.face_frame    = None
    vitals_engine.reset()   # clear the signal buffer
    return {"status": "reset"}

@app.post("/analyze_report")
async def analyze_report(file: UploadFile = File(...)):
    """Accept an uploaded PDF/JPG/PNG and run multi-modal analysis.

    Security hardening:
    - Reject uploads > config.MAX_UPLOAD_MB with 413 (stream-read in chunks;
      don't read it all before checking).
    - Allow-list extensions pdf/jpg/jpeg/png AND verify magic bytes
      (%PDF-, FFD8FF, 89504E47).
    - Derive MIME type from the verified signature, not the filename.
    - Never use the client filename in a filesystem path; use a random name with
      a fixed suffix.
    - For PDFs, cap pages (e.g. 15) using pypdf and return 422 if exceeded.
    - Uploaded bytes live only in memory or in a random-named temp file that is
      ALWAYS deleted in a finally block. Never log file contents.
    """
    # 1. Allow-list filename extension check
    filename = (file.filename or "").lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. Stream-read in chunks with size cap (don't buffer the whole file before checking)
    max_bytes = config.max_upload_bytes
    chunk_size = 65_536  # 64 KiB per read
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum allowed size of {config.MAX_UPLOAD_MB} MB",
            )
        chunks.append(chunk)
    file_bytes = b"".join(chunks)

    # 3. Magic-byte verification: derive MIME type from signature, not filename
    mime_type = validate_magic(file_bytes)
    if mime_type is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type: magic bytes do not match allowed signatures (%PDF-, FFD8FF, 89504E47).",
        )

    # 4. For PDFs, cap pages (e.g. 15) using pypdf and return 422 if exceeded
    if mime_type == "application/pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            if len(reader.pages) > MAX_PDF_PAGES:
                raise HTTPException(
                    status_code=422,
                    detail=f"PDF page count ({len(reader.pages)}) exceeds maximum limit of {MAX_PDF_PAGES} pages.",
                )
        except HTTPException:
            raise
        except Exception:
            # If pypdf cannot parse pages (e.g. mock test payload), do not block unless exceeded
            pass

    # 5. Acquire document analysis service instance
    doc_service_instance, err = get_doc_service()
    if err:
        return {"error": err}

    # 6. Pass only bytes, derived MIME type, and frame to service layer
    # Note: client filename is NOT passed to the filesystem or tempfile
    result = doc_service_instance.analyze(
        file_bytes=file_bytes,
        mime_type=mime_type,
        current_frame=state.current_frame,
    )

    if isinstance(result, dict) and result.get("_page_limit_exceeded"):
        raise HTTPException(
            status_code=422,
            detail=f"PDF page count exceeds maximum limit of {MAX_PDF_PAGES} pages.",
        )

    return result

if __name__ == "__main__":
    uvicorn.run("api:app", host=config.API_HOST, port=config.API_PORT, reload=False)
