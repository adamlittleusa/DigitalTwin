"""Shared by the SSE tests: POST one chat through the app and parse the frames it streams back."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from twin.api.app import create_app
from twin.wiring import Runtime

Frames = list[tuple[str, dict[str, Any]]]


def user(content: str) -> dict[str, str]:
    return {"role": "user", "content": content}


def stream_events(runtime: Runtime, messages: list[dict[str, str]]) -> Frames:
    """POST a chat and parse the SSE frames into (event, data) pairs, ignoring comment lines."""
    client = TestClient(create_app(runtime))
    frames: Frames = []
    with client.stream("POST", "/v1/chat", json={"messages": messages}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-store"
        event: str | None = None
        for line in response.iter_lines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:") and event is not None:
                frames.append((event, json.loads(line[len("data:") :].strip())))
                event = None
    return frames
