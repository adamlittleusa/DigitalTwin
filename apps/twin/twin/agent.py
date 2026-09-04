"""The chat-completions loop: ask the model, run any tools it asks for, repeat, bounded."""

from __future__ import annotations

from typing import Any

from twin.config import Settings
from twin.tools import ToolRegistry, dispatch

MAX_TOOL_ROUNDS = 5


class TwinAgent:
    def __init__(self, client: Any, settings: Settings, system_prompt: str, tools: ToolRegistry) -> None:
        self._client = client
        self._settings = settings
        self._system_prompt = system_prompt
        self._tools = tools

    def reply(self, history: list[dict[str, Any]], message: str) -> str:
        """Answer one user message given the prior conversation (OpenAI messages format)."""
        messages: list[Any] = [
            {"role": "system", "content": self._system_prompt},
            *history,
            {"role": "user", "content": message},
        ]
        for _ in range(MAX_TOOL_ROUNDS):
            choice = self._complete(messages, tool_choice="auto").choices[0]
            if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
                return choice.message.content or ""
            messages = [*messages, choice.message, *dispatch(self._tools, choice.message.tool_calls)]
        final = self._complete(messages, tool_choice="none").choices[0]
        return final.message.content or ""

    def _complete(self, messages: list[Any], tool_choice: str) -> Any:
        return self._client.chat.completions.create(
            model=self._settings.model,
            messages=messages,
            tools=self._tools.schemas,
            tool_choice=tool_choice,
        )
