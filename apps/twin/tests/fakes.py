"""Fakes shared by the unit tests. Nothing here touches the network."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml


class FakeClock:
    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.t = start

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def push(self, text: str) -> None:
        self.messages.append(text)


def write_md(root: Path, rel: str, meta: dict[str, Any], body: str) -> None:
    """Write one knowledge file with YAML frontmatter under root."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body + "\n", encoding="utf-8")


def project_meta(title: str) -> dict[str, Any]:
    return {"title": title, "kind": "project", "period": "2026-09 to present", "public": True}


IDENTITY_META: dict[str, Any] = {"title": "Identity", "kind": "identity", "public": True}


def chunk(
    content: str | None = None,
    frags: list[SimpleNamespace] | None = None,
    finish: str | None = None,
) -> SimpleNamespace:
    """One streamed chat-completion chunk with a single choice."""
    delta = SimpleNamespace(content=content, tool_calls=frags)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)], usage=None)


def usage_chunk(prompt: int = 100, completion: int = 20, cached: int = 50) -> SimpleNamespace:
    """The final chunk under stream_options include_usage: no choices, usage set."""
    details = SimpleNamespace(cached_tokens=cached)
    usage = SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, prompt_tokens_details=details)
    return SimpleNamespace(choices=[], usage=usage)


def frag(
    index: int,
    call_id: str | None = None,
    name: str | None = None,
    arguments: str | None = None,
) -> SimpleNamespace:
    """A streamed tool-call fragment; the first for an index carries id and name, later ones only arguments."""
    return SimpleNamespace(index=index, id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def text_stream(text: str, finish: str = "stop", with_usage: bool = True) -> list[SimpleNamespace]:
    half = len(text) // 2
    items = [chunk(content=text[:half]), chunk(content=text[half:]), chunk(finish=finish)]
    return [*items, usage_chunk()] if with_usage else items


def tool_stream(
    name: str,
    arguments: dict[str, Any],
    call_id: str = "call_1",
    leading_text: str | None = None,
) -> list[SimpleNamespace]:
    """A round in which the model asks for one tool, with its arguments split across two fragments."""
    raw = json.dumps(arguments)
    items: list[SimpleNamespace] = []
    if leading_text:
        items.append(chunk(content=leading_text))
    items += [
        chunk(frags=[frag(0, call_id=call_id, name=name, arguments=raw[:3])]),
        chunk(frags=[frag(0, arguments=raw[3:])]),
        chunk(finish="tool_calls"),
        usage_chunk(),
    ]
    return items


class ExplodingStream:
    """Yields one text chunk and then fails, like a dropped connection."""

    def __init__(self, first: SimpleNamespace | None = None) -> None:
        self._first = chunk(content="Part") if first is None else first

    def __iter__(self) -> Iterator[SimpleNamespace]:
        yield self._first
        raise RuntimeError("connection reset")


class ScriptedClient:
    """A stand-in for the OpenAI client. Returns scripted streams in order; when one is left, repeats it."""

    def __init__(self, streams: list[Any], raise_on_create: Exception | None = None) -> None:
        self._streams = list(streams)
        self._raise = raise_on_create
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._raise is not None:
            raise self._raise
        stream = self._streams.pop(0) if len(self._streams) > 1 else self._streams[0]
        return list(stream) if isinstance(stream, list) else stream


class FakeBudget:
    def __init__(self) -> None:
        self.taken = 0

    def remaining(self) -> int:
        return 999

    def take(self) -> None:
        self.taken += 1


def write_knowledge(root: Path) -> Path:
    """A two-file knowledge tree: an identity and one project."""
    write_md(root, "identity.md", IDENTITY_META, "Adam is a security leader.")
    body = "## What it is\n\nAn agent that represents Adam."
    write_md(root, "projects/digital-twin.md", project_meta("Digital twin"), body)
    return root
