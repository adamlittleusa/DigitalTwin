"""The chat-completions loop: ask the model, run any tools it asks for, repeat, bounded."""

from __future__ import annotations

import logging
from typing import Any

from twin.config import Settings
from twin.tools import ToolRegistry, dispatch

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
FALLBACK_REPLY = "I didn't manage to put an answer together just now. Could you ask that again?"


class TwinAgent:
    def __init__(self, client: Any, settings: Settings, system_prompt: str, tools: ToolRegistry) -> None:
        self._client = client
        self._settings = settings
        self._system_prompt = system_prompt
        self._tools = tools

    def reply(self, history: list[dict[str, Any]], message: str) -> str:
        """Answer one user message given the prior conversation (OpenAI messages format).

        Always returns non-empty text: the model's answer, or FALLBACK_REPLY when the model
        gave none. Tool calls are run and fed back for up to MAX_TOOL_ROUNDS rounds, then one
        final answer is requested with tools disabled.
        """
        messages: list[Any] = [
            {"role": "system", "content": self._system_prompt},
            *history,
            {"role": "user", "content": message},
        ]
        for round_number in range(1, MAX_TOOL_ROUNDS + 1):
            choice = _first_choice(self._complete(messages, tool_choice="auto"))
            if choice is None:
                return FALLBACK_REPLY
            tool_calls = choice.message.tool_calls
            if not tool_calls:
                return _text_of(choice)
            log.info("Tool round %d: %s", round_number, [_tool_name(call) for call in tool_calls])
            messages = [*messages, choice.message, *dispatch(self._tools, tool_calls)]
        log.warning("Tool round cap of %d reached; asking for a final answer without tools.", MAX_TOOL_ROUNDS)
        final = _first_choice(self._complete(messages, tool_choice="none"))
        return _text_of(final) if final is not None else FALLBACK_REPLY

    def _complete(self, messages: list[Any], tool_choice: str) -> Any:
        return self._client.chat.completions.create(
            model=self._settings.model,
            messages=messages,
            tools=self._tools.schemas,
            tool_choice=tool_choice,
        )


def _first_choice(response: Any) -> Any | None:
    choices = getattr(response, "choices", None) or []
    if not choices:
        log.warning("The model returned no choices.")
        return None
    return choices[0]


def _text_of(choice: Any) -> str:
    if choice.finish_reason == "length":
        log.warning("The reply was cut off at the model's output limit.")
    return choice.message.content or FALLBACK_REPLY


def _tool_name(call: Any) -> str:
    return getattr(getattr(call, "function", None), "name", "<unknown>")
