"""Ask the twin a fixed set of questions and print the replies and tool calls. Needs the repo .env.

Usage, from apps/twin: uv run twin-smoke
"""

from __future__ import annotations

import sys

from twin.config import load_env_file
from twin.errors import TwinError
from twin.examples import EXAMPLE_QUESTIONS
from twin.tools import RecordingTools
from twin.wiring import build_agent, load_runtime

PROBES = (
    "What's your shoe size?",
    "What's your salary?",
    "Why did you leave Corelight?",
    "Tell me about the digital twin project.",
)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_env_file()
    try:
        runtime = load_runtime()
    except TwinError as exc:
        print(f"Cannot start: {exc}", file=sys.stderr)
        return 1
    files, tokens = len(runtime.knowledge.files), runtime.knowledge.estimated_tokens
    print(f"Loaded {files} knowledge files, about {tokens} tokens.\n")
    for question in (*EXAMPLE_QUESTIONS, *PROBES):
        tools = RecordingTools()
        reply = build_agent(runtime, tools=tools).reply([], question)
        print(f"Q: {question}\nTools: {[name for name, _ in tools.calls]}\nA: {reply}\n{'-' * 72}")
    return 0
