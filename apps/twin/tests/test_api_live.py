"""Integration: one real turn through the API. Skipped without OPENAI_API_KEY."""

from __future__ import annotations

import json
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from twin.api.app import create_app
from twin.wiring import load_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"),
]


@pytest.mark.flaky(reruns=1)
def test_live_turn_streams_deltas_and_done() -> None:
    client = TestClient(create_app(load_runtime()))
    frames: list[tuple[str, dict[str, Any]]] = []
    payload = {"messages": [{"role": "user", "content": "Where are you based?"}]}
    with client.stream("POST", "/v1/chat", json=payload) as response:
        assert response.status_code == 200
        event: str | None = None
        for line in response.iter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:") and event:
                frames.append((event, json.loads(line[5:].strip())))
                event = None
    names = [name for name, _ in frames]
    assert names[0] == "step"
    assert "delta" in names
    assert names[-1] == "done"
    assert "Boston" in frames[-1][1]["reply"]
