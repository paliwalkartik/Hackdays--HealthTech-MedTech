import os
import sys
import pytest
from pathlib import Path
from config import Config, _parse_dotenv, _to_bool, config, reload


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
    assert cfg.IV_DEV_LOGIN is False
    assert cfg.IV_DISABLE_CAMERA is False
    assert cfg.IV_DISABLE_POLLING is False


def test_to_bool_helper():
    """Verify _to_bool handles strings, booleans, and edge cases."""
    for truthy in ("1", "true", "True", "TRUE", "yes", "YES", "on", "ON", True):
        assert _to_bool(truthy) is True, f"Expected {truthy} to be True"
    for falsy in ("0", "false", "False", "no", "off", "", "random", None, False):
        assert _to_bool(falsy) is False, f"Expected {falsy} to be False"


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
        "IV_DEV_LOGIN": "1",
        "IV_DISABLE_CAMERA": "true",
        "IV_DISABLE_POLLING": "yes",
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
    assert cfg.IV_DEV_LOGIN is True
    assert cfg.IV_DISABLE_CAMERA is True
    assert cfg.IV_DISABLE_POLLING is True


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
        encoding="utf-8",
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


def test_dotenv_inline_comment_stripped(tmp_path):
    """Verify inline comments are stripped when unquoted and preceded by whitespace."""
    env_file = tmp_path / ".env.inline"
    env_file.write_text(
        "FOO=bar # this is an inline comment\n"
        "BAZ=123   # another comment\n"
        "UNQUOTED_HASH=color#ff0000\n"
        "START_HASH=#full comment value\n",
        encoding="utf-8",
    )
    parsed = _parse_dotenv(env_file)
    assert parsed["FOO"] == "bar"
    assert parsed["BAZ"] == "123"
    # A '#' not preceded by whitespace is kept
    assert parsed["UNQUOTED_HASH"] == "color#ff0000"
    # A '#' at the start of value starts a comment, leaving value empty
    assert parsed["START_HASH"] == ""


def test_dotenv_quoted_hash_preserved(tmp_path):
    """Verify that quotes preserve '#' inside values, but strip trailing comments."""
    env_file = tmp_path / ".env.quoted"
    env_file.write_text(
        'KEY_DOUBLE="a # b"\n'
        "KEY_SINGLE='c # d'\n"
        'KEY_TRAILING="value # inside" # comment outside\n',
        encoding="utf-8",
    )
    parsed = _parse_dotenv(env_file)
    assert parsed["KEY_DOUBLE"] == "a # b"
    assert parsed["KEY_SINGLE"] == "c # d"
    assert parsed["KEY_TRAILING"] == "value # inside"


def test_dotenv_export_prefix(tmp_path):
    """Verify `export KEY=value` prefix is supported in .env parsing."""
    env_file = tmp_path / ".env.export"
    env_file.write_text(
        "export API_PORT=9000\n"
        'export GEMINI_MODEL="gemini-export"\n'
        "export WITH_COMMENT=val # inline comment\n",
        encoding="utf-8",
    )
    parsed = _parse_dotenv(env_file)
    assert parsed["API_PORT"] == "9000"
    assert parsed["GEMINI_MODEL"] == "gemini-export"
    assert parsed["WITH_COMMENT"] == "val"


def test_camera_backend_code():
    """Verify resolution of OpenCV VideoCapture backend flag."""
    cfg_auto = Config(CAMERA_BACKEND="auto")
    code = cfg_auto.get_camera_backend_code()
    assert isinstance(code, int)

    cfg_dshow = Config(CAMERA_BACKEND="dshow")
    assert isinstance(cfg_dshow.get_camera_backend_code(), int)

    cfg_v4l2 = Config(CAMERA_BACKEND="v4l2")
    assert isinstance(cfg_v4l2.get_camera_backend_code(), int)


def test_camera_backend_from_real_env_example():
    """Verify CAMERA_BACKEND from the real .env.example resolves to the platform backend code."""
    example_path = Path(__file__).resolve().parent.parent / ".env.example"
    assert example_path.is_file(), f".env.example not found at {example_path}"

    cfg = Config.from_env(env={}, env_file=example_path)
    assert cfg.CAMERA_BACKEND == "auto"
    code = cfg.get_camera_backend_code()
    assert isinstance(code, int)


def test_iv_dev_login_in_dotenv_makes_auth_dev_mode_true(tmp_path, monkeypatch):
    """Verify IV_DEV_LOGIN=1 in a .env makes auth.is_dev_mode() True."""
    monkeypatch.delenv("IV_DEV_LOGIN", raising=False)
    env_file = tmp_path / ".env.dev"
    env_file.write_text("IV_DEV_LOGIN=1\n", encoding="utf-8")

    import auth
    from config import config

    config.reload(env={}, env_file=env_file)
    assert config.IV_DEV_LOGIN is True
    assert auth.is_dev_mode() is True

    # Cleanup / reset
    config.reload(env={"IV_DEV_LOGIN": "0"}, env_file=None)


def test_iv_disable_camera_in_dotenv(tmp_path, monkeypatch):
    """Verify IV_DISABLE_CAMERA=1 in a .env sets config.IV_DISABLE_CAMERA to True."""
    monkeypatch.delenv("IV_DISABLE_CAMERA", raising=False)
    env_file = tmp_path / ".env.cam"
    env_file.write_text("IV_DISABLE_CAMERA=1\n", encoding="utf-8")

    cfg = Config.from_env(env={}, env_file=env_file)
    assert cfg.IV_DISABLE_CAMERA is True


def test_real_env_wins_over_dotenv(tmp_path, monkeypatch):
    """Verify real environment variables take precedence over .env file values."""
    env_file = tmp_path / ".env.precedence"
    env_file.write_text(
        "API_PORT=5555\n"
        "IV_DEV_LOGIN=0\n"
        "GEMINI_API_KEY=dotenv-gemini-key\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("API_PORT", "7777")
    monkeypatch.setenv("IV_DEV_LOGIN", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "real-os-gemini-key")

    cfg = Config.from_env(env_file=env_file)
    assert cfg.API_PORT == 7777
    assert cfg.IV_DEV_LOGIN is True
    assert cfg.GEMINI_API_KEY == "real-os-gemini-key"
    # setdefault does not overwrite real os.environ
    assert os.environ["GEMINI_API_KEY"] == "real-os-gemini-key"


def test_third_party_env_vars_exported_setdefault_only(tmp_path, monkeypatch):
    """Verify .env values are exported with setdefault ONLY for third-party vars (GEMINI_API_KEY/GOOGLE_API_KEY)."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("API_PORT", raising=False)

    env_file = tmp_path / ".env.thirdparty"
    env_file.write_text(
        "GEMINI_API_KEY=third-party-key-123\n"
        "GOOGLE_API_KEY=google-key-456\n"
        "API_PORT=9999\n",
        encoding="utf-8",
    )

    Config.from_env(env_file=env_file)
    # Third-party vars are exported to os.environ via setdefault
    assert os.environ.get("GEMINI_API_KEY") == "third-party-key-123"
    assert os.environ.get("GOOGLE_API_KEY") == "google-key-456"
    # Other variables from .env are NOT exported to os.environ
    assert os.environ.get("API_PORT") is None


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
