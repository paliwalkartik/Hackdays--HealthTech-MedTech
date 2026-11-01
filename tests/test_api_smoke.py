import io
import os
import pytest

# Ensure camera capture thread is disabled before api module is loaded
os.environ["IV_DISABLE_CAMERA"] = "1"
import api
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    os.environ["IV_DISABLE_CAMERA"] = "1"
    api.rate_limiter.reset()
    with TestClient(api.app) as test_client:
        yield test_client
    api.rate_limiter.reset()


@pytest.fixture
def auth_headers():
    return {"X-IV-Token": api.get_api_token()}


def test_health_endpoint_public(client):
    """Assert /health is public, unauthenticated, and returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_no_token_returns_401(client):
    """Assert all protected routes return 401 when no token is provided."""
    assert client.get("/vitals").status_code == 401
    assert client.get("/video_feed").status_code == 401
    assert client.post("/reset_vitals").status_code == 401
    assert client.get("/consult").status_code == 401
    assert client.post("/analyze_report").status_code == 401


def test_wrong_token_returns_401(client):
    """Assert requests with incorrect token return 401."""
    bad_headers = {"X-IV-Token": "incorrect-token-value"}
    response = client.get("/vitals", headers=bad_headers)
    assert response.status_code == 401
    assert "Unauthorized" in response.json().get("detail", "")

    # For /video_feed via query param
    feed_response = client.get("/video_feed?token=incorrect-token-value")
    assert feed_response.status_code == 401


def test_correct_token_returns_200(client, auth_headers):
    """Assert requests with correct token succeed with 200."""
    response = client.get("/vitals", headers=auth_headers)
    assert response.status_code == 200

    reset_res = client.post("/reset_vitals", headers=auth_headers)
    assert reset_res.status_code == 200
    assert reset_res.json() == {"status": "reset"}

    # /video_feed via query param stream
    token = api.get_api_token()
    with client.stream("GET", f"/video_feed?token={token}") as feed_res:
        assert feed_res.status_code == 200


def test_vitals_endpoint(client, auth_headers):
    """Assert /vitals returns the expected keys with valid types."""
    response = client.get("/vitals", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    expected_keys = {"pulse", "bpm", "is_stable", "is_completed", "stable_duration"}
    assert expected_keys.issubset(data.keys()), f"Missing keys in /vitals response: {expected_keys - set(data.keys())}"
    assert isinstance(data["pulse"], float)
    assert isinstance(data["bpm"], float)
    assert isinstance(data["is_stable"], bool)
    assert isinstance(data["is_completed"], bool)
    assert isinstance(data["stable_duration"], float)


def test_reset_vitals_endpoint(client, auth_headers):
    """Assert /reset_vitals returns {'status': 'reset'}."""
    response = client.post("/reset_vitals", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"status": "reset"}


def test_consult_missing_gemini_key_error(client, auth_headers, monkeypatch):
    """Assert /consult returns a clear error when GEMINI_API_KEY is not set."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(api.config, "GEMINI_API_KEY", "")
    api.consultant = None
    response = client.get("/consult", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "GEMINI_API_KEY" in data["error"]


def test_rate_limiting_consult(client, auth_headers):
    """Assert per-IP rate limiting allows 6 requests/min and blocks 7th with 429."""
    api.rate_limiter.reset()

    # First 6 requests should be permitted
    for i in range(6):
        res = client.get("/consult", headers=auth_headers)
        assert res.status_code == 200, f"Request {i+1} failed with status {res.status_code}"

    # 7th request must be rejected with 429 Too Many Requests
    blocked_res = client.get("/consult", headers=auth_headers)
    assert blocked_res.status_code == 429
    assert blocked_res.headers.get("Retry-After") == "60"
    assert "Rate limit exceeded" in blocked_res.json().get("detail", "")

    # Non-limited endpoint (/vitals) still works
    vitals_res = client.get("/vitals", headers=auth_headers)
    assert vitals_res.status_code == 200


def test_rate_limiting_analyze_report(client, auth_headers):
    """Assert per-IP rate limiting applies to /analyze_report."""
    api.rate_limiter.reset()
    dummy_pdf = io.BytesIO(b"%PDF-1.4 test report data")

    # First 6 requests allowed (will return 200 with error about missing gemini key or parsed)
    for i in range(6):
        dummy_pdf.seek(0)
        res = client.post(
            "/analyze_report",
            files={"file": ("report.pdf", dummy_pdf, "application/pdf")},
            headers=auth_headers,
        )
        assert res.status_code == 200, f"Request {i+1} failed with {res.status_code}"

    # 7th request must be rejected with 429
    dummy_pdf.seek(0)
    blocked_res = client.post(
        "/analyze_report",
        files={"file": ("report.pdf", dummy_pdf, "application/pdf")},
        headers=auth_headers,
    )
    assert blocked_res.status_code == 429
    assert blocked_res.headers.get("Retry-After") == "60"
    assert "Rate limit exceeded" in blocked_res.json().get("detail", "")
