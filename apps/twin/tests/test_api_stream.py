"""AgentStream on its own: a synchronous turn run in a thread, consumed as an async iterator."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

from twin.agent import FALLBACK_REPLY
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
