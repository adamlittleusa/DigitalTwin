"""Runtime settings, read from the environment and validated once at startup."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
DEFAULT_ENV_FILE = REPO_ROOT / ".env"
REQUIRED_VARS: tuple[str, ...] = ("OPENAI_API_KEY",)


class ConfigError(Exception):
    """Raised when required configuration is missing."""


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    model: str
    knowledge_dir: Path
    pushover_user: str | None
    pushover_token: str | None

    @property
    def pushover_enabled(self) -> bool:
        return bool(self.pushover_user and self.pushover_token)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        source: Mapping[str, str] = os.environ if env is None else env
        missing = [name for name in REQUIRED_VARS if not source.get(name)]
        if missing:
            raise ConfigError("Missing required environment variables: " + ", ".join(missing))
        knowledge_dir = source.get("KNOWLEDGE_DIR")
        return cls(
            openai_api_key=source["OPENAI_API_KEY"],
            model=source.get("TWIN_MODEL") or DEFAULT_MODEL,
            knowledge_dir=Path(knowledge_dir) if knowledge_dir else DEFAULT_KNOWLEDGE_DIR,
            pushover_user=source.get("PUSHOVER_USER") or None,
            pushover_token=source.get("PUSHOVER_TOKEN") or None,
        )


def load_env_file(path: Path | None = None) -> None:
    """Load a .env file into os.environ. Safe to call when the file is absent.

    The default is resolved at call time so a script can point DEFAULT_ENV_FILE
    elsewhere before calling.
    """
    from dotenv import load_dotenv

    load_dotenv(DEFAULT_ENV_FILE if path is None else path, override=True)
