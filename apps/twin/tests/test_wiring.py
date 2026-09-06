from pathlib import Path

import pytest

from tests.fakes import IDENTITY_META, FakeClock, project_meta, write_md
from twin.config import ConfigError
from twin.limits import DailyBudget, RateLimitedNotifier, RateLimiter
from twin.tools import LoggingNotifier, PushoverNotifier, RecordingTools, TwinTools
from twin.wiring import Runtime, build_agent, load_runtime


@pytest.fixture
def knowledge_dir(tmp_path: Path) -> Path:
    write_md(tmp_path, "identity.md", IDENTITY_META, "Adam is a security leader.")
    write_md(tmp_path, "projects/digital-twin.md", project_meta("Digital twin"), "## What it is\n\nAn agent.")
    return tmp_path


def env_for(knowledge_dir: Path, **extra: str) -> dict[str, str]:
    return {"OPENAI_API_KEY": "sk-test", "KNOWLEDGE_DIR": str(knowledge_dir), **extra}


def test_load_runtime_assembles_everything(knowledge_dir: Path) -> None:
    client = object()
    runtime = load_runtime(env_for(knowledge_dir, TWIN_SITE_URL="https://x"), client=client, clock=FakeClock())
    assert isinstance(runtime, Runtime)
    assert runtime.client is client
    assert len(runtime.knowledge.files) == 2
    assert runtime.catalog.slugs == ("digital-twin",)
    card = runtime.catalog.get("digital-twin")
    assert card is not None and card.url == "https://x/projects/digital-twin"
    assert '<section kind="identity"' in runtime.system_prompt
    assert isinstance(runtime.notifier, RateLimitedNotifier)
    assert isinstance(runtime.limiter, RateLimiter)
    assert isinstance(runtime.budget, DailyBudget)
    assert runtime.prompt_cache_key.startswith("twin-prompt-")
    assert len(runtime.prompt_cache_key) == len("twin-prompt-") + 12
    assert runtime.log_salt


def test_prompt_cache_key_is_stable_for_the_same_knowledge(knowledge_dir: Path) -> None:
    a = load_runtime(env_for(knowledge_dir), client=object(), clock=FakeClock())
    b = load_runtime(env_for(knowledge_dir), client=object(), clock=FakeClock())
    assert a.prompt_cache_key == b.prompt_cache_key


def test_load_runtime_fails_fast_without_the_key(knowledge_dir: Path) -> None:
    with pytest.raises(ConfigError):
        load_runtime({"KNOWLEDGE_DIR": str(knowledge_dir)}, client=object(), clock=FakeClock())


def test_notifier_is_logging_when_pushover_is_unset(knowledge_dir: Path) -> None:
    runtime = load_runtime(env_for(knowledge_dir), client=object(), clock=FakeClock())
    assert isinstance(runtime.notifier, RateLimitedNotifier)
    assert isinstance(runtime.notifier.inner, LoggingNotifier)


def test_notifier_is_pushover_when_configured(knowledge_dir: Path) -> None:
    env = env_for(knowledge_dir, PUSHOVER_USER="u-abc", PUSHOVER_TOKEN="t-abc")
    runtime = load_runtime(env, client=object(), clock=FakeClock())
    assert isinstance(runtime.notifier, RateLimitedNotifier)
    assert isinstance(runtime.notifier.inner, PushoverNotifier)


def test_build_agent_uses_runtime_pieces(knowledge_dir: Path) -> None:
    runtime = load_runtime(env_for(knowledge_dir), client=object(), clock=FakeClock())
    agent = build_agent(runtime, safety_identifier="abc")
    assert isinstance(agent._tools, TwinTools)
    assert agent._catalog is runtime.catalog
    assert agent._budget is runtime.budget
    assert agent._prompt_cache_key == runtime.prompt_cache_key
    assert agent._safety_identifier == "abc"


def test_build_agent_accepts_an_injected_registry(knowledge_dir: Path) -> None:
    runtime = load_runtime(env_for(knowledge_dir), client=object(), clock=FakeClock())
    tools = RecordingTools()
    assert build_agent(runtime, tools=tools)._tools is tools


def test_explicit_salt_is_used(knowledge_dir: Path) -> None:
    runtime = load_runtime(env_for(knowledge_dir, TWIN_LOG_SALT="pepper"), client=object(), clock=FakeClock())
    assert runtime.log_salt == "pepper"
