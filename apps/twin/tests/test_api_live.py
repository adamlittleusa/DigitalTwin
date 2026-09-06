"""Integration: one real turn through the API. Skipped without OPENAI_API_KEY."""

from __future__ import annotations

import dataclasses
import os

import pytest

from tests.sse import stream_events, user
from twin.tools import LoggingNotifier
from twin.wiring import load_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"),
]


@pytest.mark.flaky(reruns=1)
def test_live_turn_streams_deltas_and_done() -> None:
    runtime = dataclasses.replace(load_runtime(), notifier=LoggingNotifier())
    frames = stream_events(runtime, [user("Where are you based?")])
    names = [name for name, _ in frames]
    assert names[0] == "step"
    assert "delta" in names
    assert "agent_error" not in names
    assert names[-1] == "done"
    assert "Boston" in frames[-1][1]["reply"]
