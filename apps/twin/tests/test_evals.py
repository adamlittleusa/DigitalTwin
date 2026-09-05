"""Integration evals: run every case in evals/twin_qa.yaml through the real model."""

from __future__ import annotations

import os
from collections.abc import Callable

import pytest
from openai import OpenAI

from twin.agent import TwinAgent
from twin.config import REPO_ROOT, Settings
from twin.evals import EvalCase, check, load_cases
from twin.knowledge import load_knowledge
from twin.prompt import build_system_prompt
from twin.tools import RecordingTools, ToolRegistry

EVAL_FILE = REPO_ROOT / "evals" / "twin_qa.yaml"
CASES = load_cases(EVAL_FILE)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"),
]

AgentFactory = Callable[[ToolRegistry], TwinAgent]


@pytest.fixture(scope="module")
def agent_factory() -> AgentFactory:
    settings = Settings.from_env()
    system_prompt = build_system_prompt(load_knowledge(settings.knowledge_dir))
    client = OpenAI(api_key=settings.openai_api_key)

    def make(tools: ToolRegistry) -> TwinAgent:
        return TwinAgent(client, settings, system_prompt, tools)

    return make


@pytest.mark.flaky(reruns=1)
@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_eval_case(agent_factory: AgentFactory, case: EvalCase) -> None:
    tools = RecordingTools()
    reply = agent_factory(tools).reply([], case.question)
    failures = check(case, reply, [name for name, _ in tools.calls])
    assert not failures, f"{case.id}: {'; '.join(failures)}\n--- reply ---\n{reply}"
