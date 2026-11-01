import sys
import pytest
from pathlib import Path
from config import Config, _parse_dotenv


def test_default_config():
    """Verify that default config values match specification."""
    cfg = Config()
    assert cfg.API_HOST == "127.0.0.1"
    assert cfg.API_PORT == 8000
    assert cfg.API_BASE_URL == "http://127.0.0.1:8000"
    assert cfg.CAMERA_INDEX == 0
    assert cfg.CAMERA_BACKEND == "auto"
    assert cfg.GEMINI_API_KEY == ""
    assert cfg.GEMINI_MODEL == "gemini-2.5-flash"
    assert cfg.MEASURE_SECONDS == 60.0
    assert cfg.WINDOW_SECONDS == 10
    assert cfg.MAX_UPLOAD_MB == 10
    assert cfg.max_upload_bytes == 10 * 1024 * 1024
    assert cfg.DB_PATH == "health_data.db"
    assert cfg.ALLOWED_ORIGINS == ["http://localhost:8501"]
    assert cfg.SESSION_TTL_DAYS == 30


def test_config_from_custom_env(monkeypatch):
    """Verify Config.from_env parses custom environment variables and types correctly."""
    custom_env = {
        "API_HOST": "0.0.0.0",
        "API_PORT": "8080",
        "API_BASE_URL": "https://api.example.com",
        "CAMERA_INDEX": "2",
        "CAMERA_BACKEND": "dshow",
        "GEMINI_API_KEY": "test-key-12345",
        "GEMINI_MODEL": "gemini-2.0-flash",
        "MEASURE_SECONDS": "45.5",
        "WINDOW_SECONDS": "12",
        "MAX_UPLOAD_MB": "25",
        "DB_PATH": "test_db.sqlite",
        "ALLOWED_ORIGINS": "https://app1.test, https://app2.test",
        "SESSION_TTL_DAYS": "14",
    }
    cfg = Config.from_env(env=custom_env)

    assert cfg.API_HOST == "0.0.0.0"
    assert cfg.API_PORT == 8080
    assert cfg.API_BASE_URL == "https://api.example.com"
    assert cfg.CAMERA_INDEX == 2
    assert cfg.CAMERA_BACKEND == "dshow"
    assert cfg.GEMINI_API_KEY == "test-key-12345"
    assert cfg.GEMINI_MODEL == "gemini-2.0-flash"
    assert cfg.MEASURE_SECONDS == 45.5
    assert cfg.WINDOW_SECONDS == 12
    assert cfg.MAX_UPLOAD_MB == 25
    assert cfg.max_upload_bytes == 25 * 1024 * 1024
    assert cfg.DB_PATH == "test_db.sqlite"
    assert cfg.ALLOWED_ORIGINS == ["https://app1.test", "https://app2.test"]
    assert cfg.SESSION_TTL_DAYS == 14


def test_config_base_url_derived_from_host_port():
    """Verify API_BASE_URL automatically derives from API_HOST and API_PORT if not explicit."""
    cfg = Config.from_env(env={"API_HOST": "10.0.0.5", "API_PORT": "9000"})
    assert cfg.API_BASE_URL == "http://10.0.0.5:9000"


def test_dotenv_parser(tmp_path):
    """Verify parsing of .env format files with quotes and comments."""
    env_file = tmp_path / ".env.test"
    env_file.write_text(
        "# Comment line\n"
        "API_PORT=9090\n"
        'GEMINI_MODEL="gemini-custom"\n'
        "DB_PATH='custom_health.db'\n"
        "EMPTY_VAL=\n"
        "INVALID_LINE_NO_EQUALS\n",
        encoding="utf-8"
    )

    parsed = _parse_dotenv(env_file)
    assert parsed["API_PORT"] == "9090"
    assert parsed["GEMINI_MODEL"] == "gemini-custom"
    assert parsed["DB_PATH"] == "custom_health.db"
    assert parsed["EMPTY_VAL"] == ""
    assert "INVALID_LINE_NO_EQUALS" not in parsed

    cfg = Config.from_env(env={}, env_file=env_file)
    assert cfg.API_PORT == 9090
    assert cfg.GEMINI_MODEL == "gemini-custom"
    assert cfg.DB_PATH == "custom_health.db"


def test_camera_backend_code():
    """Verify resolution of OpenCV VideoCapture backend flag."""
    cfg_auto = Config(CAMERA_BACKEND="auto")
    code = cfg_auto.get_camera_backend_code()
    assert isinstance(code, int)

    cfg_dshow = Config(CAMERA_BACKEND="dshow")
    assert isinstance(cfg_dshow.get_camera_backend_code(), int)

    cfg_v4l2 = Config(CAMERA_BACKEND="v4l2")
    assert isinstance(cfg_v4l2.get_camera_backend_code(), int)


def test_config_api_token_and_headers(monkeypatch):
    """Verify api_token resolution and HTTP authentication headers dict."""
    monkeypatch.delenv("IV_API_TOKEN", raising=False)
    cfg = Config(IV_API_TOKEN="secret-token-123")
    assert cfg.api_token == "secret-token-123"
    assert cfg.api_headers == {"X-IV-Token": "secret-token-123"}

    cfg_empty = Config(IV_API_TOKEN="")
    assert cfg_empty.api_headers == {}

    # Falls back to os.environ if IV_API_TOKEN field is empty
    monkeypatch.setenv("IV_API_TOKEN", "env-token-456")
    assert cfg_empty.api_token == "env-token-456"
    assert cfg_empty.api_headers == {"X-IV-Token": "env-token-456"}


