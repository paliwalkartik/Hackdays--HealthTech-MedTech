import os
import pytest

# Ensure camera capture thread is disabled before api module is loaded
os.environ["IV_DISABLE_CAMERA"] = "1"
import api
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    os.environ["IV_DISABLE_CAMERA"] = "1"
    with TestClient(api.app) as test_client:
        yield test_client


def test_vitals_endpoint(client):
    """Assert /vitals returns the expected keys with valid types."""
    response = client.get("/vitals")
    assert response.status_code == 200
    data = response.json()
    expected_keys = {"pulse", "bpm", "is_stable", "is_completed", "stable_duration"}
    assert expected_keys.issubset(data.keys()), f"Missing keys in /vitals response: {expected_keys - set(data.keys())}"
    assert isinstance(data["pulse"], float)
    assert isinstance(data["bpm"], float)
    assert isinstance(data["is_stable"], bool)
    assert isinstance(data["is_completed"], bool)
    assert isinstance(data["stable_duration"], float)


def test_reset_vitals_endpoint(client):
    """Assert /reset_vitals returns {'status': 'reset'}."""
    response = client.post("/reset_vitals")
    assert response.status_code == 200
    assert response.json() == {"status": "reset"}


def test_consult_missing_gemini_key_error(client, monkeypatch):
    """Assert /consult returns a clear error when GEMINI_API_KEY is not set."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(api.config, "GEMINI_API_KEY", "")
    # Reset cached consultant client
    api.consultant = None
    response = client.get("/consult")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "GEMINI_API_KEY" in data["error"]

