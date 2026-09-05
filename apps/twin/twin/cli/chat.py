"""Chat with the twin in the terminal and watch the loop work. Development only.

Usage, from apps/twin: uv run twin-chat
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from twin.agent import TwinAgent
from twin.config import load_env_file
from twin.errors import TwinError
from twin.events import Delta, Done, Error, Project, Step, ToolCall, ToolResult
from twin.examples import EXAMPLE_QUESTIONS
from twin.wiring import build_agent, load_runtime

log = logging.getLogger("twin.chat")
EXIT_WORDS = frozenset({"exit", "quit", "q"})


def print_turn(agent: TwinAgent, history: list[dict[str, Any]], message: str) -> str:
    """Stream one turn to the terminal, showing loop steps in brackets, and return the reply."""
    reply = ""
    for event in agent.run(history, message):
        if isinstance(event, Step):
            print(f"\n  [{event.phase}, round {event.round}]", flush=True)
            if event.phase == "composing":
                print("\ntwin> ", end="", flush=True)
        elif isinstance(event, ToolCall):
            print(f"  [tool: {event.label}]", flush=True)
        elif isinstance(event, ToolResult):
            print(f"  [tool {'ok' if event.ok else 'failed'}]", flush=True)
        elif isinstance(event, Delta):
            print(event.text, end="", flush=True)
        elif isinstance(event, Project):
            print(f"\n  [project card: {event.title} -> {event.url}]", flush=True)
        elif isinstance(event, Error):
            print(f"\n  [error: {event.message}]", flush=True)
        elif isinstance(event, Done):
            reply = event.reply
    print()
    return reply


def run_repl(agent: TwinAgent) -> None:
    history: list[dict[str, Any]] = []
    print("Digital Twin. Type a question, or 'exit' to quit. Examples:")
    for question in EXAMPLE_QUESTIONS:
        print(f"  - {question}")
    while True:
        try:
            message = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not message:
            continue
        if message.lower() in EXIT_WORDS:
            return
        try:
            reply = print_turn(agent, history, message)
        except KeyboardInterrupt:
            print("\n(cancelled)")
            continue
        history = [*history, {"role": "user", "content": message}, {"role": "assistant", "content": reply}]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # the OpenAI SDK's HTTP client logs every request
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # replies may contain non-cp1252 characters
    load_env_file()
    try:
        runtime = load_runtime()
    except TwinError as exc:
        log.error("Cannot start: %s", exc)
        return 1
    files, tokens = len(runtime.knowledge.files), runtime.knowledge.estimated_tokens
    log.info("Loaded %d knowledge files, about %d tokens.", files, tokens)
    run_repl(build_agent(runtime))
    return 0
