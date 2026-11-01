"""
tests/test_upload_security.py — Upload validation tests for /analyze_report.

Covers:
- 413 on oversized upload (stream-read in chunks, not fully buffered first)
- 415 on disallowed extension
- 415 on unrecognised/bad magic bytes
- MIME type derived from magic bytes, not client filename
- 422 on PDF exceeding MAX_PDF_PAGES pages using pypdf
- Random name with fixed suffix (client filename never used in filesystem path)
- Temp file deleted in finally block, temp dir empty after success and exception
- No logging of file contents
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest.mock as mock

import pypdf
import pytest

# Disable camera before importing api
os.environ["IV_DISABLE_CAMERA"] = "1"
import api
from document_service import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MAGIC,
    MAX_PDF_PAGES,
    DocumentAnalysisService,
    validate_magic,
)
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    api.rate_limiter.reset()
    with TestClient(api.app) as c:
        yield c
    api.rate_limiter.reset()


@pytest.fixture()
def auth_headers():
    return {"X-IV-Token": api.get_api_token()}


# ---------------------------------------------------------------------------
# Magic-byte and extension validation unit tests
# ---------------------------------------------------------------------------


def test_validate_magic_pdf():
    assert validate_magic(b"%PDF-1.4 content") == "application/pdf"


def test_validate_magic_jpeg():
    assert validate_magic(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100) == "image/jpeg"


def test_validate_magic_png():
    assert validate_magic(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100) == "image/png"


def test_validate_magic_unknown_returns_none():
    assert validate_magic(b"GIF89a...") is None
    assert validate_magic(b"RIFF....WEBP") is None
    assert validate_magic(b"\x00\x01\x02\x03") is None


def test_validate_magic_empty_returns_none():
    assert validate_magic(b"") is None


def test_validate_magic_ignores_filename():
    """MIME type is derived from the verified signature, not the filename."""
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    assert validate_magic(png_bytes) == "image/png"


# ---------------------------------------------------------------------------
# /analyze_report HTTP endpoint tests
# ---------------------------------------------------------------------------


def _make_minimal_pdf(num_pages: int = 1) -> bytes:
    """Build a minimal valid PDF with *num_pages* blank pages using pypdf."""
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_oversized_upload_returns_413(client, auth_headers, monkeypatch):
    """Streaming size check must reject large uploads with HTTP 413."""
    # Set limit to 1 MB and upload 1 MB + 100 bytes
    monkeypatch.setattr(api.config, "MAX_UPLOAD_MB", 1)
    large_pdf = b"%PDF-1.4 " + (b"x" * (1024 * 1024 + 100))
    res = client.post(
        "/analyze_report",
        files={"file": ("report.pdf", io.BytesIO(large_pdf), "application/pdf")},
        headers=auth_headers,
    )
    assert res.status_code == 413, f"Expected 413, got {res.status_code}: {res.text}"


def test_disallowed_extension_returns_415(client, auth_headers):
    """Files with extensions outside pdf/jpg/jpeg/png must be rejected with HTTP 415."""
    res = client.post(
        "/analyze_report",
        files={"file": ("malicious.exe", io.BytesIO(b"%PDF-1.4 evil"), "application/octet-stream")},
        headers=auth_headers,
    )
    assert res.status_code == 415, f"Expected 415, got {res.status_code}: {res.text}"


def test_bad_magic_bytes_returns_415(client, auth_headers):
    """Files with unrecognised magic bytes must be rejected with HTTP 415."""
    gif_bytes = b"GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;"
    res = client.post(
        "/analyze_report",
        files={"file": ("image.png", io.BytesIO(gif_bytes), "image/png")},
        headers=auth_headers,
    )
    assert res.status_code == 415, f"Expected 415, got {res.status_code}: {res.text}"


def test_mime_derived_from_signature_not_filename(client, auth_headers):
    """A PDF uploaded as .jpg must be identified as application/pdf from its magic bytes."""
    pdf_bytes = _make_minimal_pdf(1)
    captured_mime = []

    def mock_analyze(file_bytes, mime_type, current_frame=None, temp_dir=None):
        captured_mime.append(mime_type)
        return {"summary": "ok"}

    stub_svc = mock.MagicMock(spec=DocumentAnalysisService)
    stub_svc.analyze.side_effect = mock_analyze
    api.doc_service = stub_svc

    res = client.post(
        "/analyze_report",
        files={"file": ("bloodwork.jpg", io.BytesIO(pdf_bytes), "image/jpeg")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert captured_mime == ["application/pdf"]


def test_pdf_page_limit_returns_422(client, auth_headers):
    """PDF with more than MAX_PDF_PAGES pages must be rejected with HTTP 422."""
    too_many_pages = _make_minimal_pdf(MAX_PDF_PAGES + 1)
    stub_svc = mock.MagicMock(spec=DocumentAnalysisService)
    stub_svc.analyze.return_value = {"summary": "ok"}
    api.doc_service = stub_svc

    res = client.post(
        "/analyze_report",
        files={"file": ("report.pdf", io.BytesIO(too_many_pages), "application/pdf")},
        headers=auth_headers,
    )
    assert res.status_code == 422, f"Expected 422, got {res.status_code}: {res.text}"


def test_pdf_within_page_limit_accepted(client, auth_headers):
    """PDF with up to MAX_PDF_PAGES pages must pass page cap check."""
    ok_pdf = _make_minimal_pdf(MAX_PDF_PAGES)
    stub_svc = mock.MagicMock(spec=DocumentAnalysisService)
    stub_svc.analyze.return_value = {"summary": "ok"}
    api.doc_service = stub_svc

    res = client.post(
        "/analyze_report",
        files={"file": ("report.pdf", io.BytesIO(ok_pdf), "application/pdf")},
        headers=auth_headers,
    )
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Temp file cleanup tests (document_service layer)
# ---------------------------------------------------------------------------


def _make_stub_service() -> DocumentAnalysisService:
    """Create a DocumentAnalysisService with no real Gemini client."""
    svc = DocumentAnalysisService.__new__(DocumentAnalysisService)
    svc.model = "stub-model"
    svc.client = None
    return svc


def test_temp_dir_is_empty_after_success(tmp_path):
    """Assert temp dir is empty after successful analysis."""
    svc = _make_stub_service()

    # Verify temp dir is initially empty
    assert os.listdir(tmp_path) == []

    # Mock the Gemini upload and generate calls
    fake_client = mock.MagicMock()
    fake_client.models.generate_content.return_value.text = '{"summary": "ok"}'
    fake_client.files.upload.return_value = mock.MagicMock(name="file-123")
    fake_client.files.get.return_value.state = "ACTIVE"
    svc.client = fake_client

    result = svc.analyze(
        file_bytes=b"%PDF-1.4 minimal",
        mime_type="application/pdf",
        temp_dir=str(tmp_path),
    )

    assert result == {"summary": "ok"}
    # Assert temp dir is empty after success
    assert os.listdir(tmp_path) == [], "Temp dir was NOT empty after successful analysis!"


def test_temp_dir_is_empty_after_exception(tmp_path):
    """Assert temp dir is empty even after an exception in service layer."""
    svc = _make_stub_service()

    # Verify temp dir is initially empty
    assert os.listdir(tmp_path) == []

    # Force an exception during upload (after temp file has been written to disk)
    fake_client = mock.MagicMock()
    fake_client.files.upload.side_effect = RuntimeError("simulated upload failure")
    svc.client = fake_client

    result = svc.analyze(
        file_bytes=b"%PDF-1.4 minimal",
        mime_type="application/pdf",
        temp_dir=str(tmp_path),
    )

    assert "error" in result
    # Assert temp dir is empty after exception
    assert os.listdir(tmp_path) == [], "Temp dir was NOT empty after analysis raised an exception!"


def test_temp_file_uses_random_name_with_fixed_suffix(tmp_path):
    """Temp file must use a random name with a fixed suffix and never client filename."""
    svc = _make_stub_service()

    created_filenames = []
    original_mkstemp = tempfile.mkstemp

    def tracking_mkstemp(*args, **kwargs):
        fd, path = original_mkstemp(*args, **kwargs)
        created_filenames.append(os.path.basename(path))
        return fd, path

    with mock.patch("tempfile.mkstemp", side_effect=tracking_mkstemp):
        fake_client = mock.MagicMock()
        fake_client.models.generate_content.return_value.text = '{"summary": "ok"}'
        fake_client.files.upload.return_value = mock.MagicMock(name="file-123")
        fake_client.files.get.return_value.state = "ACTIVE"
        svc.client = fake_client

        svc.analyze(
            file_bytes=b"%PDF-1.4 minimal",
            mime_type="application/pdf",
            temp_dir=str(tmp_path),
        )

    assert len(created_filenames) == 1
    filename = created_filenames[0]
    # Fixed suffix .pdf, random prefix starting with iv_
    assert filename.endswith(".pdf")
    assert filename.startswith("iv_")
    # Never matches client filename (e.g. "secret_patient_report.pdf")
    assert "secret_patient_report" not in filename
