"""The chat-completions loop as a stream of events: ask the model, run any tools it asks for, repeat, bounded."""

from __future__ import annotations

import json
import logging
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from twin.config import Settings
from twin.events import AgentEvent, Delta, Done, Error, Project, Step, ToolCall, ToolResult, Usage, label_for
from twin.projects import ProjectCard, ProjectCatalog
from twin.tools import ToolRegistry, dispatch, is_failure

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5
FALLBACK_REPLY = "I didn't manage to put an answer together just now. Could you ask that again?"
MODEL_ERROR_MESSAGE = "I lost my train of thought there. Could you ask that again?"


class Budget(Protocol):
    def take(self) -> None: ...


@dataclass(frozen=True)
class _Function:
    name: str
    arguments: str


@dataclass(frozen=True)
class _Call:
    """A completed tool call in the attribute shape `dispatch` reads."""

    id: str
    function: _Function

    def as_message_part(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.function.name, "arguments": self.function.arguments},
        }

    def slug(self) -> str | None:
        try:
            parsed = json.loads(self.function.arguments or "{}")
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        value = parsed.get("slug")
        return value if isinstance(value, str) else None


@dataclass(frozen=True)
class _Round:
    text: str
    calls: tuple[_Call, ...]
    finish_reason: str | None
    usage: Usage | None
    saw_choice: bool
    composing: bool


class TwinAgent:
    def __init__(
        self,
        client: Any,
        settings: Settings,
        system_prompt: str,
        tools: ToolRegistry,
        *,
        safety_identifier: str | None = None,
        prompt_cache_key: str | None = None,
        budget: Budget | None = None,
        catalog: ProjectCatalog | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._system_prompt = system_prompt
        self._tools = tools
        self._safety_identifier = safety_identifier
        self._prompt_cache_key = prompt_cache_key
        self._budget = budget
        self._catalog = catalog

    def reply(self, history: list[dict[str, Any]], message: str) -> str:
        """Answer one user message given the prior conversation. Always non-empty; never raises."""
        reply = FALLBACK_REPLY
        for event in self.run(history, message):
            if isinstance(event, Done):
                reply = event.reply
        return reply

    def run(self, history: list[dict[str, Any]], message: str) -> Iterator[AgentEvent]:
        """One turn as a stream of events. Exactly one Done, always last; never raises."""
        messages: list[Any] = [
            {"role": "system", "content": self._system_prompt},
            *history,
            {"role": "user", "content": message},
        ]
        buffer: list[str] = []  # every delta text, so Done.reply matches what the visitor saw even after a failure
        tools_used: list[str] = []
        shown: set[str] = set()
        usage: Usage | None = None
        rounds = 0
        composing = False
        try:
            for round_number in range(1, MAX_TOOL_ROUNDS + 1):
                yield Step("thinking", round_number)
                rounds += 1
                round_ = yield from self._stream_round(messages, "auto", round_number, composing, buffer)
                composing = round_.composing
                usage = _add_usage(usage, round_.usage)
                if not round_.calls:
                    if not round_.saw_choice:
                        log.warning("The model returned no choices.")
                    yield Done("".join(buffer) or FALLBACK_REPLY, tuple(tools_used), rounds, usage)
                    return
                log.info("Tool round %d: %s", round_number, [call.function.name for call in round_.calls])
                for call in round_.calls:
                    yield ToolCall(call.function.name, label_for(call.function.name))
                results = dispatch(self._tools, round_.calls)
                for call, result in zip(round_.calls, results, strict=True):
                    ok = _ok(result)
                    tools_used.append(call.function.name)
                    yield ToolResult(call.function.name, ok)
                    card = self._card_for(call) if ok else None
                    if card is not None and card.slug not in shown:
                        shown.add(card.slug)
                        yield Project(card.slug, card.title, card.summary, card.url)
                messages = [*messages, _assistant_message(round_), *results]
            log.warning("Tool round cap of %d reached; asking for a final answer without tools.", MAX_TOOL_ROUNDS)
            yield Step("thinking", MAX_TOOL_ROUNDS + 1)
            rounds += 1
            final = yield from self._stream_round(messages, "none", MAX_TOOL_ROUNDS + 1, composing, buffer)
            usage = _add_usage(usage, final.usage)
            yield Done("".join(buffer) or FALLBACK_REPLY, tuple(tools_used), rounds, usage)
        except Exception:
            log.exception("The model call failed")
            yield Error("model_error", MODEL_ERROR_MESSAGE)
            yield Done("".join(buffer) or FALLBACK_REPLY, tuple(tools_used), rounds, usage)

    def _stream_round(
        self,
        messages: list[Any],
        tool_choice: str,
        round_number: int,
        composing: bool,
        buffer: list[str],
    ) -> Generator[AgentEvent, None, _Round]:
        """Stream one model call, yielding composing and delta events; returns the round's summary.

        Delta text is appended to `buffer` as it is yielded so a failure mid-stream loses nothing.
        """
        if self._budget is not None:
            self._budget.take()
        stream = self._client.chat.completions.create(
            model=self._settings.model,
            messages=messages,
            tools=self._tools.schemas,
            tool_choice=tool_choice,
            stream=True,
            stream_options={"include_usage": True},
            timeout=self._settings.model_timeout_seconds,
            **self._identity_kwargs(),
        )
        parts: dict[int, dict[str, str]] = {}
        text: list[str] = []
        finish: str | None = None
        usage: Usage | None = None
        saw_choice = False
        for chunk in stream:
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage is not None:
                usage = _usage_from(chunk_usage)
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            saw_choice = True
            choice = choices[0]
            delta = getattr(choice, "delta", None)
            if delta is not None:
                content = getattr(delta, "content", None)
                if content:
                    if not composing:
                        composing = True
                        yield Step("composing", round_number)
                    text.append(content)
                    buffer.append(content)
                    yield Delta(content)
                for fragment in getattr(delta, "tool_calls", None) or []:
                    _absorb(parts, fragment)
            if getattr(choice, "finish_reason", None):
                finish = choice.finish_reason
        if finish == "length":
            log.warning("The reply was cut off at the model's output limit.")
        calls = tuple(_call_from(part) for _, part in sorted(parts.items()))
        return _Round("".join(text), calls, finish, usage, saw_choice, composing)

    def _identity_kwargs(self) -> dict[str, str]:
        extra: dict[str, str] = {}
        if self._safety_identifier:
            extra["safety_identifier"] = self._safety_identifier
        if self._prompt_cache_key:
            extra["prompt_cache_key"] = self._prompt_cache_key
        return extra

    def _card_for(self, call: _Call) -> ProjectCard | None:
        if call.function.name != "show_project" or self._catalog is None:
            return None
        slug = call.slug()
        return self._catalog.get(slug) if slug else None


def _absorb(parts: dict[int, dict[str, str]], fragment: Any) -> None:
    """Merge one streamed tool-call fragment into the accumulator for its index."""
    slot = parts.setdefault(getattr(fragment, "index", 0), {"id": "", "name": "", "arguments": ""})
    call_id = getattr(fragment, "id", None)
    if call_id:
        slot["id"] = call_id
    function = getattr(fragment, "function", None)
    if function is not None:
        name = getattr(function, "name", None)
        if name:
            slot["name"] = name
        arguments = getattr(function, "arguments", None)
        if arguments:
            slot["arguments"] += arguments


def _call_from(part: dict[str, str]) -> _Call:
    return _Call(id=part["id"], function=_Function(part["name"], part["arguments"]))


def _assistant_message(round_: _Round) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": round_.text or None,
        "tool_calls": [call.as_message_part() for call in round_.calls],
    }


def _ok(tool_message: dict[str, Any]) -> bool:
    try:
        result = json.loads(tool_message["content"])
    except (KeyError, TypeError, json.JSONDecodeError):
        return False
    return isinstance(result, str) and not is_failure(result)


def _usage_from(raw: Any) -> Usage:
    details = getattr(raw, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None) or 0
    return Usage(
        prompt_tokens=getattr(raw, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(raw, "completion_tokens", 0) or 0,
        cached_tokens=cached,
    )


def _add_usage(total: Usage | None, more: Usage | None) -> Usage | None:
    if more is None:
        return total
    return more if total is None else total + more
