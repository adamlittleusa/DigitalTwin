"""One place that assembles the twin: settings, knowledge, prompt, notifier, client, limits, agent."""

from __future__ import annotations

import hashlib
import logging
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from twin.agent import TwinAgent
from twin.config import Settings
from twin.knowledge import Knowledge, load_knowledge
from twin.limits import Clock, DailyBudget, RateLimitedNotifier, RateLimiter, SystemClock
from twin.projects import ProjectCatalog
from twin.prompt import build_system_prompt
from twin.tools import LoggingNotifier, Notifier, PushoverNotifier, ToolRegistry, TwinTools

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Runtime:
    settings: Settings
    knowledge: Knowledge
    catalog: ProjectCatalog
    system_prompt: str
    notifier: Notifier
    client: Any
    clock: Clock
    limiter: RateLimiter
    budget: DailyBudget
    prompt_cache_key: str
    log_salt: str


def load_runtime(
    env: Mapping[str, str] | None = None,
    *,
    client: Any | None = None,
    clock: Clock | None = None,
) -> Runtime:
    """The single startup path. Raises TwinError subclasses; callers print one line and exit."""
    settings = Settings.from_env(env)
    knowledge = load_knowledge(settings.knowledge_dir)
    catalog = ProjectCatalog.from_knowledge(knowledge, settings.site_url)
    system_prompt = build_system_prompt(knowledge)
    ticking = clock if clock is not None else SystemClock()
    return Runtime(
        settings=settings,
        knowledge=knowledge,
        catalog=catalog,
        system_prompt=system_prompt,
        notifier=choose_notifier(settings, ticking),
        client=client if client is not None else OpenAI(api_key=settings.openai_api_key),
        clock=ticking,
        limiter=RateLimiter(settings.per_client_hourly, settings.per_client_burst, ticking),
        budget=DailyBudget(settings.daily_call_limit, ticking),
        prompt_cache_key="twin-prompt-" + hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:12],
        log_salt=settings.log_salt or secrets.token_hex(16),
    )


def choose_notifier(settings: Settings, clock: Clock) -> Notifier:
    """Pushover when configured, the log otherwise; either way capped per hour."""
    inner: Notifier
    if settings.pushover_enabled:
        inner = PushoverNotifier(settings.pushover_user or "", settings.pushover_token or "")
    else:
        log.warning("Pushover is not configured; notifications will be logged instead of pushed.")
        inner = LoggingNotifier()
    return RateLimitedNotifier(inner, settings.pushover_hourly, clock)


def build_agent(
    runtime: Runtime,
    *,
    tools: ToolRegistry | None = None,
    safety_identifier: str | None = None,
) -> TwinAgent:
    """A fresh agent for one turn or one request."""
    registry = tools if tools is not None else TwinTools(runtime.notifier, catalog=runtime.catalog)
    return TwinAgent(
        runtime.client,
        runtime.settings,
        runtime.system_prompt,
        registry,
        safety_identifier=safety_identifier,
        prompt_cache_key=runtime.prompt_cache_key,
        budget=runtime.budget,
        catalog=runtime.catalog,
    )
