"""Chat with the twin in the terminal. Development only, not part of the deployment story.

Usage, from apps/twin: uv run python scripts/chat.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # replies may contain non-cp1252 characters

from openai import OpenAI, OpenAIError  # noqa: E402

from twin.agent import TwinAgent  # noqa: E402
from twin.config import ConfigError, Settings, load_env_file  # noqa: E402
from twin.examples import EXAMPLE_QUESTIONS  # noqa: E402
from twin.knowledge import Knowledge, KnowledgeError, load_knowledge  # noqa: E402
from twin.prompt import build_system_prompt  # noqa: E402
from twin.tools import LoggingNotifier, Notifier, PushoverNotifier, TwinTools  # noqa: E402

log = logging.getLogger("twin.chat")
EXIT_WORDS = frozenset({"exit", "quit", "q"})


def choose_notifier(settings: Settings) -> Notifier:
    if settings.pushover_enabled:
        return PushoverNotifier(settings.pushover_user or "", settings.pushover_token or "")
    log.warning("Pushover is not configured; notifications will be logged instead of pushed.")
    return LoggingNotifier()


def build_agent(settings: Settings, knowledge: Knowledge) -> TwinAgent:
    client = OpenAI(api_key=settings.openai_api_key)
    return TwinAgent(
        client=client,
        settings=settings,
        system_prompt=build_system_prompt(knowledge),
        tools=TwinTools(choose_notifier(settings)),
    )


def run_repl(agent: TwinAgent) -> None:
    history: list[dict[str, object]] = []
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
            reply = agent.reply(history, message)
        except OpenAIError as exc:
            log.error("The model call failed: %s", exc)
            continue
        except KeyboardInterrupt:
            print("\n(cancelled)")
            continue
        print(f"\ntwin> {reply}")
        history = [*history, {"role": "user", "content": message}, {"role": "assistant", "content": reply}]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # the OpenAI SDK's HTTP client logs every request at INFO
    load_env_file()
    try:
        settings = Settings.from_env()
        knowledge = load_knowledge(settings.knowledge_dir)
    except (ConfigError, KnowledgeError) as exc:
        log.error("Cannot start: %s", exc)
        return 1
    log.info("Loaded %d knowledge files, about %d tokens.", len(knowledge.files), knowledge.estimated_tokens)
    run_repl(build_agent(settings, knowledge))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
