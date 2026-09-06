"""The streaming pieces on their own, driven with asyncio.run rather than a TestClient: AgentStream, a
synchronous turn run in a thread and consumed as an async iterator, and the SSE response that carries it."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Iterator

from starlette.types import Message, Scope

from twin.agent import FALLBACK_REPLY
from twin.api.routes import _TurnResponse
from twin.api.stream import AgentStream
from twin.events import AgentEvent, Delta, Done, Error, Step


async def collect(stream: AgentStream) -> list[AgentEvent]:
    return [event async for event in stream]


def test_agent_stream_forwards_events_then_ends() -> None:
    def turn() -> Iterator[AgentEvent]:
        yield Step("thinking", 1)
        yield Delta("Hi")

    assert asyncio.run(collect(AgentStream(turn))) == [Step("thinking", 1), Delta("Hi")]


def test_agent_stream_reports_a_turn_that_raises() -> None:
    def turn() -> Iterator[AgentEvent]:
        raise RuntimeError("boom")
        yield Step("thinking", 1)  # unreachable; it makes this a generator like a real turn

    assert asyncio.run(collect(AgentStream(turn))) == [
        Error("internal", "Something went wrong on our side."),
        Done(FALLBACK_REPLY, (), 0, None),
    ]


def test_in_flight_is_released_when_send_fails_before_the_first_frame() -> None:
    """sse-starlette cancels its tasks at the first failed send, before the generator is ever entered, so a
    finally inside the generator would never run; the response's own finally is what releases the slot."""
    entered = False
    releases = 0

    async def events() -> AsyncIterator[dict[str, str]]:
        nonlocal entered
        entered = True
        yield {"event": "delta", "data": "{}"}

    def release() -> None:
        nonlocal releases
        releases += 1

    async def receive() -> Message:
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        raise RuntimeError("socket closed")

    async def run() -> None:
        scope: Scope = {"type": "http", "method": "POST", "path": "/v1/chat", "headers": []}
        response = _TurnResponse(events(), release=release)
        with contextlib.suppress(RuntimeError):
            await response(scope, receive, send)

    asyncio.run(run())
    assert releases == 1
    assert entered is False
