"""Runtime settings, read from the environment and validated once at startup."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

from twin.errors import TwinError


def _repo_root() -> Path:
    """The repository root when the package runs from the source tree (the nearest ancestor
    holding apps/ and knowledge/); the working directory otherwise."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "knowledge").is_dir() and (parent / "apps").is_dir():
            return parent
    return Path.cwd()


REPO_ROOT = _repo_root()
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
DEFAULT_ALLOWED_ORIGINS: tuple[str, ...] = ("http://localhost:3000",)
DEFAULT_SITE_URL = "https://adambuilds.ai"
REQUIRED_VARS: tuple[str, ...] = ("OPENAI_API_KEY",)
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


class ConfigError(TwinError):
    """Raised when required configuration is missing or a value cannot be parsed."""


def _read(source: Mapping[str, str], name: str) -> str:
    """The variable's value with surrounding whitespace removed, or '' when unset."""
    return (source.get(name) or "").strip()


def _int(
    source: Mapping[str, str], name: str, default: int, *, minimum: int = 0, maximum: int | None = None
) -> int:
    raw = _read(source, name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from None
    if value < minimum or (maximum is not None and value > maximum):
        if maximum is None:
            raise ConfigError(f"{name} must be at least {minimum}, got {raw!r}")
        raise ConfigError(f"{name} must be between {minimum} and {maximum}, got {raw!r}")
    return value


def _positive_float(source: Mapping[str, str], name: str, default: float) -> float:
    raw = _read(source, name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if not math.isfinite(value) or value <= 0:
        raise ConfigError(f"{name} must be a finite number greater than zero, got {raw!r}")
    return value


def _flag(source: Mapping[str, str], name: str, default: bool) -> bool:
    raw = _read(source, name).lower()
    if not raw:
        return default
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ConfigError(f"{name} must be true or false, got {raw!r}")


def _csv(source: Mapping[str, str], name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = _read(source, name)
    if not raw:
        return default
    items = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not items:
        raise ConfigError(f"{name} is set but contains no values")
    return items


def _origin(name: str, value: str) -> str:
    """The origin with any trailing slash removed, once it is confirmed to be a bare origin."""
    parts = urlsplit(value)
    path = parts.path[:-1] if parts.path.endswith("/") else parts.path
    if parts.scheme not in {"http", "https"} or not parts.netloc or path or parts.query or parts.fragment:
        raise ConfigError(f"{name} must be an origin like https://example.com, got {value!r}")
    return value[:-1] if value.endswith("/") else value


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = field(repr=False)
    model: str
    knowledge_dir: Path
    pushover_user: str | None = field(repr=False)
    pushover_token: str | None = field(repr=False)
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS
    site_url: str = DEFAULT_SITE_URL
    trust_proxy: bool = False
    log_salt: str | None = field(default=None, repr=False)
    per_client_hourly: int = 20
    per_client_burst: int = 5
    max_user_messages: int = 8
    daily_call_limit: int = 500
    pushover_hourly: int = 10
    model_timeout_seconds: float = 60.0
    port: int = 8080

    @property
    def pushover_enabled(self) -> bool:
        return bool(self.pushover_user and self.pushover_token)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        source: Mapping[str, str] = os.environ if env is None else env
        missing = [name for name in REQUIRED_VARS if not _read(source, name)]
        if missing:
            raise ConfigError("Missing required environment variables: " + ", ".join(missing))
        knowledge_dir = _read(source, "KNOWLEDGE_DIR")
        trust_proxy = _flag(source, "TWIN_TRUST_PROXY", False)
        log_salt = _read(source, "TWIN_LOG_SALT") or None
        if trust_proxy and not log_salt:
            raise ConfigError("TWIN_LOG_SALT is required when TWIN_TRUST_PROXY is true")
        return cls(
            openai_api_key=_read(source, "OPENAI_API_KEY"),
            model=_read(source, "TWIN_MODEL") or DEFAULT_MODEL,
            knowledge_dir=Path(knowledge_dir).expanduser() if knowledge_dir else DEFAULT_KNOWLEDGE_DIR,
            pushover_user=_read(source, "PUSHOVER_USER") or None,
            pushover_token=_read(source, "PUSHOVER_TOKEN") or None,
            allowed_origins=tuple(
                _origin("TWIN_ALLOWED_ORIGINS", item)
                for item in _csv(source, "TWIN_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
            ),
            site_url=_origin("TWIN_SITE_URL", _read(source, "TWIN_SITE_URL") or DEFAULT_SITE_URL),
            trust_proxy=trust_proxy,
            log_salt=log_salt,
            per_client_hourly=_int(source, "TWIN_PER_CLIENT_HOURLY", 20),
            per_client_burst=_int(source, "TWIN_PER_CLIENT_BURST", 5),
            max_user_messages=_int(source, "TWIN_MAX_USER_MESSAGES", 8),
            daily_call_limit=_int(source, "TWIN_DAILY_CALL_LIMIT", 500),
            pushover_hourly=_int(source, "TWIN_PUSHOVER_HOURLY", 10),
            model_timeout_seconds=_positive_float(source, "TWIN_MODEL_TIMEOUT_SECONDS", 60.0),
            port=_int(source, "PORT", 8080, minimum=1, maximum=65535),
        )


def load_env_file(path: Path | None = None) -> None:
    """Load a .env file into os.environ. Safe to call when the file is absent.

    The default is resolved at call time so a script can point DEFAULT_ENV_FILE
    elsewhere before calling.
    """
    load_dotenv(DEFAULT_ENV_FILE if path is None else path, override=True)
