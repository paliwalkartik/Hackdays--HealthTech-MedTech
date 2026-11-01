"""
config.py — Intelli-Vitals Central Configuration

Loads configuration from environment variables and optional .env file.
Provides typed access to server, camera, database, model, and application settings.
Config is the single source of truth for application settings.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

# Variables that third-party SDKs (such as google-genai) read directly from os.environ
THIRD_PARTY_ENV_VARS: tuple[str, ...] = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


def _to_bool(val: Any) -> bool:
    """Coerce value to boolean ("1", "true", "yes", "on" are True)."""
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _parse_dotenv(dotenv_path: Path | str) -> Dict[str, str]:
    """Parse a KEY=VALUE formatted .env file.

    Supports:
    - Quoted values: "value" or 'value' (retains internal '#' characters).
    - Inline comments: '#' starts a comment only if at the start of the value
      or preceded by whitespace when unquoted.
    - 'export KEY=value' prefix.
    - Blank lines and full-line comments starting with '#'.
    """
    values: Dict[str, str] = {}
    path = Path(dotenv_path)
    if not path.is_file():
        return values

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Support optional 'export ' prefix (e.g. `export KEY=value`)
                if line.startswith("export") and (len(line) > 6 and line[6].isspace()):
                    line = line[6:].lstrip()

                if "=" not in line:
                    continue

                k, _, v = line.partition("=")
                key = k.strip()
                if not key:
                    continue

                val = v.strip()
                # Parse value: handle quotes vs inline comments
                if val and val[0] in ('"', "'"):
                    quote_char = val[0]
                    # Find closing quote
                    closing_idx = -1
                    i = 1
                    while i < len(val):
                        if val[i] == quote_char:
                            if quote_char == '"' and val[i - 1] == "\\":
                                i += 1
                                continue
                            closing_idx = i
                            break
                        i += 1

                    if closing_idx != -1:
                        raw_inside = val[1:closing_idx]
                        if quote_char == '"':
                            raw_inside = raw_inside.replace('\\"', '"').replace("\\n", "\n")
                        values[key] = raw_inside
                    else:
                        # Unclosed quote: strip outer quote
                        values[key] = val.strip(quote_char)
                else:
                    # Unquoted: '#' starts a comment only when at start of value or preceded by whitespace
                    if val.startswith("#"):
                        values[key] = ""
                    else:
                        match = re.search(r"\s+#", val)
                        if match:
                            val = val[:match.start()]
                        values[key] = val.strip()
    except OSError:
        pass
    return values


@dataclass
class Config:
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    API_BASE_URL: str = "http://127.0.0.1:8000"
    CAMERA_INDEX: int = 0
    CAMERA_BACKEND: str = "auto"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    MEASURE_SECONDS: float = 60.0
    WINDOW_SECONDS: int = 10
    MAX_UPLOAD_MB: int = 10
    DB_PATH: str = "health_data.db"
    ALLOWED_ORIGINS: List[str] = field(default_factory=lambda: ["http://localhost:8501"])
    SESSION_TTL_DAYS: int = 30
    IV_API_TOKEN: str = ""
    IV_DEV_LOGIN: bool = False
    IV_DISABLE_CAMERA: bool = False
    IV_DISABLE_POLLING: bool = False

    def __getattribute__(self, name: str) -> Any:
        # Dynamically read os.environ at call time for the global config singleton
        if name in ("IV_DEV_LOGIN", "IV_DISABLE_CAMERA", "IV_DISABLE_POLLING"):
            if "config" in globals() and self is globals()["config"]:
                if name in os.environ:
                    return _to_bool(os.environ[name])
        return super().__getattribute__(name)

    @classmethod
    def from_env(
        cls,
        env: Dict[str, str] | None = None,
        env_file: Path | str | None = None,
    ) -> Config:
        """Create a Config instance from explicit env dict or os.environ + optional .env."""
        # 1. Parse .env file if present
        dotenv_values: Dict[str, str] = {}
        if env_file is None:
            default_env = Path(".env")
            if default_env.exists():
                dotenv_values = _parse_dotenv(default_env)
        else:
            p = Path(env_file)
            if p.exists():
                dotenv_values = _parse_dotenv(p)

        # 2. Export .env values into os.environ with setdefault ONLY for third-party SDK vars,
        # never overriding real environment variables.
        for var_name in THIRD_PARTY_ENV_VARS:
            if var_name in dotenv_values and dotenv_values[var_name]:
                os.environ.setdefault(var_name, dotenv_values[var_name])

        # 3. Merge hierarchy: .env < os.environ < explicitly passed env dict
        merged: Dict[str, str] = {}
        merged.update(dotenv_values)
        merged.update(os.environ)
        if env is not None:
            merged.update(env)

        api_host = merged.get("API_HOST", "127.0.0.1").strip()
        try:
            api_port = int(merged.get("API_PORT", "8000"))
        except ValueError:
            api_port = 8000

        # API_BASE_URL defaults to http://<API_HOST>:<API_PORT> if not provided
        if "API_BASE_URL" in merged and merged["API_BASE_URL"].strip():
            api_base_url = merged["API_BASE_URL"].strip().rstrip("/")
        else:
            api_base_url = f"http://{api_host}:{api_port}"

        try:
            camera_index = int(merged.get("CAMERA_INDEX", "0"))
        except ValueError:
            camera_index = 0

        camera_backend = merged.get("CAMERA_BACKEND", "auto").strip().lower()

        gemini_api_key = merged.get("GEMINI_API_KEY", "").strip()
        gemini_model = merged.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

        try:
            measure_seconds = float(merged.get("MEASURE_SECONDS", "60"))
        except ValueError:
            measure_seconds = 60.0

        try:
            window_seconds = int(merged.get("WINDOW_SECONDS", "10"))
        except ValueError:
            window_seconds = 10

        try:
            max_upload_mb = int(merged.get("MAX_UPLOAD_MB", "10"))
        except ValueError:
            max_upload_mb = 10

        db_path = merged.get("DB_PATH", "health_data.db").strip()

        raw_origins = merged.get("ALLOWED_ORIGINS", "http://localhost:8501")
        if isinstance(raw_origins, list):
            allowed_origins = [str(o).strip() for o in raw_origins if str(o).strip()]
        else:
            allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
        if not allowed_origins:
            allowed_origins = ["http://localhost:8501"]

        try:
            session_ttl_days = int(merged.get("SESSION_TTL_DAYS", "30"))
        except ValueError:
            session_ttl_days = 30

        iv_api_token = merged.get("IV_API_TOKEN", "").strip()
        iv_dev_login = _to_bool(merged.get("IV_DEV_LOGIN", "0"))
        iv_disable_camera = _to_bool(merged.get("IV_DISABLE_CAMERA", "0"))
        iv_disable_polling = _to_bool(merged.get("IV_DISABLE_POLLING", "0"))

        return cls(
            API_HOST=api_host,
            API_PORT=api_port,
            API_BASE_URL=api_base_url,
            CAMERA_INDEX=camera_index,
            CAMERA_BACKEND=camera_backend,
            GEMINI_API_KEY=gemini_api_key,
            GEMINI_MODEL=gemini_model,
            MEASURE_SECONDS=measure_seconds,
            WINDOW_SECONDS=window_seconds,
            MAX_UPLOAD_MB=max_upload_mb,
            DB_PATH=db_path,
            ALLOWED_ORIGINS=allowed_origins,
            SESSION_TTL_DAYS=session_ttl_days,
            IV_API_TOKEN=iv_api_token,
            IV_DEV_LOGIN=iv_dev_login,
            IV_DISABLE_CAMERA=iv_disable_camera,
            IV_DISABLE_POLLING=iv_disable_polling,
        )

    def reload(
        self,
        env: Dict[str, str] | None = None,
        env_file: Path | str | None = None,
    ) -> Config:
        """Reload configuration from environment and optional .env file."""
        new_cfg = Config.from_env(env=env, env_file=env_file)
        for k, v in new_cfg.__dict__.items():
            setattr(self, k, v)
        return self

    @property
    def api_token(self) -> str:
        """API token for service-to-service communication."""
        return self.IV_API_TOKEN or os.environ.get("IV_API_TOKEN", "").strip()

    @property
    def api_headers(self) -> Dict[str, str]:
        """HTTP headers required to authenticate with the API backend."""
        token = self.api_token
        if token:
            return {"X-IV-Token": token}
        return {}

    def get_camera_backend_code(self) -> int:
        """Resolve OpenCV VideoCapture backend flag based on CAMERA_BACKEND."""
        backend = self.CAMERA_BACKEND.lower().strip()
        try:
            import cv2
        except ImportError:
            return 0

        if backend == "dshow":
            return getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY)
        if backend == "v4l2":
            return getattr(cv2, "CAP_V4L2", cv2.CAP_ANY)
        if backend == "avfoundation":
            return getattr(cv2, "CAP_AVFOUNDATION", cv2.CAP_ANY)
        if backend == "auto":
            if sys.platform.startswith("win"):
                return getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY)
            if sys.platform.startswith("linux"):
                return getattr(cv2, "CAP_V4L2", cv2.CAP_ANY)
            if sys.platform == "darwin":
                return getattr(cv2, "CAP_AVFOUNDATION", cv2.CAP_ANY)
            return getattr(cv2, "CAP_ANY", 0)

        return getattr(cv2, "CAP_ANY", 0)

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


# Global singleton instance loaded from environment / .env
config = Config.from_env()


def reload(
    env: Dict[str, str] | None = None,
    env_file: Path | str | None = None,
) -> Config:
    """Reload the global config singleton."""
    return config.reload(env=env, env_file=env_file)
