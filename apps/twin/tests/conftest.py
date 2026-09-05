"""Shared pytest setup. Loads the repo .env so integration tests can find the API key, and offers API fixtures."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.fakes import FakeClock, ScriptedClient, text_stream, write_knowledge
from twin.config import load_env_file

load_env_file()


@pytest.fixture
def knowledge_dir(tmp_path: Path) -> Path:
    return write_knowledge(tmp_path / "knowledge")


@pytest.fixture
def make_runtime(knowledge_dir: Path) -> Callable[..., Any]:
    """Build a Runtime on a fake clock and a scripted model client; keyword arguments become environment variables."""
    from twin.wiring import Runtime, load_runtime

    def factory(streams: list[Any] | None = None, clock: FakeClock | None = None, **env: str) -> Runtime:
        client = ScriptedClient(streams if streams is not None else [text_stream("Hello from the twin.")])
        base = {"OPENAI_API_KEY": "sk-test", "KNOWLEDGE_DIR": str(knowledge_dir), "TWIN_SITE_URL": "https://x"}
        return load_runtime({**base, **env}, client=client, clock=clock or FakeClock())

    return factory
