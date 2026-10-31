"""
document_service.py — Medical Report Analysis via Gemini File API

Uploads a PDF or JPG report using genai.upload_file, then sends it
alongside the patient's current webcam frame for a multi-modal analysis.
"""

import os
import time
import tempfile
import json
import cv2
from PIL import Image

from google import genai

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


class DocumentAnalysisService:
    def __init__(self, api_key: str = None):
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
        self.client = genai.Client()

    def _upload_report(self, file_path: str, mime_type: str):
        """Upload a local file to Gemini File API and wait until it is ACTIVE."""
        print(f"[DocumentService] Uploading {file_path} as {mime_type}...")
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
        print(f"[DocumentService] File ready: {file_ref.name}")
        return file_ref

    def _frame_to_pil(self, bgr_frame) -> Image.Image:
        """Convert an OpenCV BGR frame to a PIL RGB image."""
        if bgr_frame is None:
            return None
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def analyze(self, file_bytes: bytes, filename: str, current_frame=None) -> dict:
        """
        Parameters
        ----------
        file_bytes   : raw bytes of the uploaded PDF / JPG / PNG
        filename     : original filename (used to infer MIME type)
        current_frame: optional OpenCV BGR numpy array (webcam frame)

        Returns
        -------
        dict with structured analysis fields (or an 'error' key on failure)
        """
        ext = filename.lower().rsplit(".", 1)[-1]
        mime_map = {
            "pdf":  "application/pdf",
            "jpg":  "image/jpeg",
            "jpeg": "image/jpeg",
            "png":  "image/png",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")

        # Write to a temp file so we can pass a path to the File API
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            file_ref = self._upload_report(tmp_path, mime_type)

            # Build contents list: prompt + uploaded report + optional webcam frame
            contents = [ANALYSIS_PROMPT, file_ref]
            pil_frame = self._frame_to_pil(current_frame)
            if pil_frame is not None:
                contents.append(pil_frame)

            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
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
            return {"error": str(exc)}

        finally:
            os.unlink(tmp_path)
