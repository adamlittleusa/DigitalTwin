"""Ask the twin a fixed set of questions and print the replies. Needs the repo .env.

Usage, from apps/twin: uv run python scripts/smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # replies may contain non-cp1252 characters

from openai import OpenAI  # noqa: E402

from twin.agent import TwinAgent  # noqa: E402
from twin.config import Settings, load_env_file  # noqa: E402
from twin.examples import EXAMPLE_QUESTIONS  # noqa: E402
from twin.knowledge import load_knowledge  # noqa: E402
from twin.prompt import build_system_prompt  # noqa: E402
from twin.tools import RecordingTools  # noqa: E402

PROBES = (
    "What's your shoe size?",
    "What's your salary?",
    "Why did you leave Corelight?",
)


def main() -> int:
    load_env_file()
    settings = Settings.from_env()
    knowledge = load_knowledge(settings.knowledge_dir)
    print(f"Loaded {len(knowledge.files)} knowledge files, about {knowledge.estimated_tokens} tokens.\n")
    client = OpenAI(api_key=settings.openai_api_key)
    system_prompt = build_system_prompt(knowledge)
    for question in (*EXAMPLE_QUESTIONS, *PROBES):
        tools = RecordingTools()
        reply = TwinAgent(client, settings, system_prompt, tools).reply([], question)
        print(f"Q: {question}\nTools: {[name for name, _ in tools.calls]}\nA: {reply}\n{'-' * 72}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
