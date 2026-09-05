"""Runtime settings, read from the environment and validated once at startup."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from twin.errors import TwinError

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
REQUIRED_VARS: tuple[str, ...] = ("OPENAI_API_KEY",)


class ConfigError(TwinError):
    """Raised when required configuration is missing."""


def _read(source: Mapping[str, str], name: str) -> str:
    """The variable's value with surrounding whitespace removed, or '' when unset."""
    return (source.get(name) or "").strip()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = field(repr=False)
    model: str
    knowledge_dir: Path
    pushover_user: str | None
    pushover_token: str | None = field(repr=False)

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
        return cls(
            openai_api_key=_read(source, "OPENAI_API_KEY"),
            model=_read(source, "TWIN_MODEL") or DEFAULT_MODEL,
            knowledge_dir=Path(knowledge_dir).expanduser() if knowledge_dir else DEFAULT_KNOWLEDGE_DIR,
            pushover_user=_read(source, "PUSHOVER_USER") or None,
            pushover_token=_read(source, "PUSHOVER_TOKEN") or None,
        )


def load_env_file(path: Path | None = None) -> None:
    """Load a .env file into os.environ. Safe to call when the file is absent.

    The default is resolved at call time so a script can point DEFAULT_ENV_FILE
    elsewhere before calling.
    """
    load_dotenv(DEFAULT_ENV_FILE if path is None else path, override=True)
