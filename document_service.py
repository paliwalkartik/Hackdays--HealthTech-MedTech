"""
document_service.py — Medical Report Analysis via Gemini File API

Security notes:
- MIME type is derived from magic bytes, never from the client-supplied filename.
- The client filename is never used in any filesystem path.
- Uploaded bytes are written to a random-named temp file that is ALWAYS deleted
  in a finally block, regardless of success or failure.
- PDF page count is capped at MAX_PDF_PAGES (422 sentinel returned if exceeded).
- File contents are never logged.
- Remote deletion of the provider-side file is deferred to AI-6 (LLM fallback).
"""

from __future__ import annotations

import io
import logging
import os
import secrets
import tempfile
import json
from typing import Optional

import cv2
from PIL import Image

from config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Magic-byte allow-list
# ---------------------------------------------------------------------------

# Allowed file extensions
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

# Each entry: (mime_type, fixed_suffix_for_tempfile, magic_bytes_prefix)
ALLOWED_MAGIC: list[tuple[str, str, bytes]] = [
    ("application/pdf", ".pdf", b"%PDF-"),
    ("image/jpeg",      ".jpg", b"\xFF\xD8\xFF"),
    ("image/png",       ".png", b"\x89PNG"),
]

# Minimum prefix length needed to identify any signature (longest magic prefix)
_MAGIC_PROBE = max(len(m) for _, _, m in ALLOWED_MAGIC)

# Maximum pages allowed in an uploaded PDF
MAX_PDF_PAGES: int = 15


def validate_magic(data: bytes) -> Optional[str]:
    """Return the MIME type derived from magic bytes, or None if unrecognised.

    Only the bytes in ``data`` are examined — the caller's filename is ignored.
    """
    probe = data[:_MAGIC_PROBE]
    for mime_type, _suffix, magic in ALLOWED_MAGIC:
        if probe.startswith(magic):
            return mime_type
    return None


def _suffix_for_mime(mime_type: str) -> str:
    mapping = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
    }
    return mapping.get(mime_type, ".bin")


# ---------------------------------------------------------------------------
# Gemini analysis prompt
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """
You are a senior consultant physician and medical AI expert.

You have been given TWO inputs:
1. A patient's medical report (PDF or image).
2. A live webcam photo showing the patient's current facial appearance.

Your task:
- Carefully read the medical report.
- Observe the patient's facial appearance for visible health cues (pallor, swelling, jaundice, distress, etc.).
- Cross-reference the findings.

Return a comprehensive clinical assessment in the following strict JSON format (no markdown, no code blocks):
{
  "summary": "One-sentence plain-English summary of the report",
  "health_risks": ["Risk 1", "Risk 2", "Risk 3"],
  "visual_observations": "What the patient's face reveals about their current condition",
  "lifestyle_measures": ["Measure 1", "Measure 2", "Measure 3"],
  "medical_specialty": "The primary medical specialty required (e.g., Cardiology, Neurology, Endocrinology)",
  "urgency_level": "Routine / Soon / Urgent",
  "action_plan": "Concrete next step the patient should take"
}
"""


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------

class DocumentAnalysisService:
    def __init__(self, api_key: str = None, model: str = None):
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
        self.model = model or config.GEMINI_MODEL
        from google import genai
        self.client = genai.Client()

    def _upload_report(self, file_path: str, mime_type: str):
        """Upload a local file to Gemini File API and wait until it is ACTIVE.

        Remote deletion of the provider-side file is handled in AI-6.
        File path is logged only at DEBUG level; contents are never logged.
        """
        import time
        from google import genai
        logger.debug("[DocumentService] Uploading temp file as %s", mime_type)
        file_ref = self.client.files.upload(
            file=file_path,
            config={"mime_type": mime_type},
        )
        # Poll until the file is ACTIVE (processing can take a few seconds for PDFs)
        for _ in range(20):
            state = self.client.files.get(name=file_ref.name).state
            if str(state) in ("FileState.ACTIVE", "ACTIVE", "2"):  # SDK returns enum
                break
            time.sleep(1)
        logger.debug("[DocumentService] Provider file ready: %s", file_ref.name)
        return file_ref

    def _frame_to_pil(self, bgr_frame) -> Optional[Image.Image]:
        """Convert an OpenCV BGR frame to a PIL RGB image."""
        if bgr_frame is None:
            return None
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def _check_pdf_pages(self, file_bytes: bytes) -> bool:
        """Return True if the PDF page count is within MAX_PDF_PAGES, False otherwise."""
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            return len(reader.pages) <= MAX_PDF_PAGES
        except Exception:
            # If we can't parse it, let the provider attempt it anyway
            return True

    def analyze(
        self,
        file_bytes: bytes,
        mime_type: str,
        current_frame=None,
        temp_dir: str | None = None,
    ) -> dict:
        """Analyse an uploaded medical report.

        Parameters
        ----------
        file_bytes   : raw bytes of the uploaded PDF / JPEG / PNG
        mime_type    : MIME type derived from magic bytes (caller's responsibility)
        current_frame: optional OpenCV BGR numpy array (webcam frame)
        temp_dir     : optional directory for temp file creation

        Returns
        -------
        dict with structured analysis fields, an 'error' key on failure, or
        ``{"_page_limit_exceeded": True}`` when the PDF is too long.
        """
        # --- PDF page cap (before writing to disk / sending to provider) ---
        if mime_type == "application/pdf":
            if not self._check_pdf_pages(file_bytes):
                logger.warning(
                    "[DocumentService] PDF rejected: exceeds %d pages", MAX_PDF_PAGES
                )
                return {"_page_limit_exceeded": True}

        # --- Write to a random-named temp file; NEVER use the client filename ---
        suffix = _suffix_for_mime(mime_type)
        # Use a random hex prefix so the name is unpredictable even on shared systems
        random_prefix = f"iv_{secrets.token_hex(8)}_"
        tmp_fd, tmp_path = tempfile.mkstemp(dir=temp_dir, prefix=random_prefix, suffix=suffix)
        os.close(tmp_fd)

        try:
            with open(tmp_path, "wb") as fh:
                fh.write(file_bytes)

            file_ref = self._upload_report(tmp_path, mime_type)

            # Build contents list: prompt + uploaded report + optional webcam frame
            contents = [ANALYSIS_PROMPT, file_ref]
            pil_frame = self._frame_to_pil(current_frame)
            if pil_frame is not None:
                contents.append(pil_frame)

            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
            )
            raw = response.text.strip()

            # Strip markdown fences if the model added them
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.startswith("```"):
                raw = raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]

            return json.loads(raw.strip())

        except Exception as exc:
            logger.error("[DocumentService] Analysis failed: %s", exc)
            return {"error": str(exc)}

        finally:
            # Always delete the temp file — even if an exception was raised
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.warning("[DocumentService] Could not delete temp file: %s", tmp_path)
