from google import genai
import os
import cv2
from PIL import Image
import json

class ClinicalConsultant:
    def __init__(self, api_key=None):
        # Using Gemini 1.5 Flash as requested
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
        self.client = genai.Client()

    def analyze(self, bpm_data, face_frame):
        """
        bpm_data: list of BPM values over the 10-second window
        face_frame: OpenCV BGR image (numpy array)
        """
        if face_frame is None:
            return {"error": "No face frame provided", "clinical_status": "Unknown"}

        # Convert OpenCV BGR image to PIL Image (RGB)
        rgb_frame = cv2.cvtColor(face_frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)

        avg_bpm = sum(bpm_data) / len(bpm_data) if bpm_data else 0

        prompt = f"""
        You are a senior clinical consultant AI. Analyze the patient's face visually and their heart rate data.
        Over the last 10 seconds, their BPM data was: {bpm_data}. The average BPM is {avg_bpm:.1f}.
        Return a JSON-formatted "Clinical Snapshot" with the following keys:
        - "average_bpm": Number
        - "visual_assessment": String (analyze their facial expression, apparent stress level, or paleness)
        - "clinical_status": String (e.g., "Normal", "Elevated Heart Rate", "Requires Attention")
        - "recommendation": String (A brief actionable suggestion)
        Do NOT wrap the response in markdown blocks like ```json ... ```. Just return raw JSON.
        """

        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, pil_image]
            )
            result_text = response.text.strip()
            
            # Clean up potential markdown formatting from the response
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            
            result_text = result_text.strip()
            return json.loads(result_text)
        except Exception as e:
            return {"error": str(e), "average_bpm": avg_bpm, "clinical_status": "Unknown"}
