from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tests.fakes import ExplodingStream, text_stream, tool_stream
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


def only(frames: Frames, *names: str) -> Frames:
    return [f for f in frames if f[0] in names]


def test_text_turn_event_sequence(make_runtime: Callable[..., Runtime]) -> None:
    frames = stream_events(make_runtime([text_stream("Hello.")]), [user("hi")])
    assert [name for name, _ in frames] == ["step", "step", "delta", "delta", "done"]
    assert frames[0][1] == {"phase": "thinking", "round": 1}
    assert frames[1][1] == {"phase": "composing", "round": 1}
    assert "".join(data["text"] for name, data in frames if name == "delta") == "Hello."
    assert frames[-1][1] == {"reply": "Hello.", "rounds": 1}


def test_tool_turn_shows_a_label_and_never_a_name(make_runtime: Callable[..., Runtime]) -> None:
    runtime = make_runtime([tool_stream("record_sensitive_question", {"question": "why?"}), text_stream("Wrapped up.")])
    frames = stream_events(runtime, [user("why did you leave?")])
    assert [name for name, _ in frames] == ["step", "tool", "tool_result", "step", "step", "delta", "delta", "done"]
    assert frames[1][1] == {"label": "Passing this along to Adam"}
    assert frames[2][1] == {"ok": True}
    for _, data in frames:
        assert "name" not in data and "tools" not in data and "usage" not in data


def test_unknown_and_sensitive_produce_identical_tool_frames(make_runtime: Callable[..., Runtime]) -> None:
    unknown = make_runtime([tool_stream("record_unknown_question", {"question": "q"}), text_stream("x")])
    sensitive = make_runtime([tool_stream("record_sensitive_question", {"question": "q"}), text_stream("x")])
    a = stream_events(unknown, [user("q")])
    b = stream_events(sensitive, [user("q")])
    assert only(a, "tool", "tool_result") == only(b, "tool", "tool_result")


def test_project_card_frame(make_runtime: Callable[..., Runtime]) -> None:
    runtime = make_runtime([tool_stream("show_project", {"slug": "digital-twin"}), text_stream("Here.")])
    frames = stream_events(runtime, [user("what are you building?")])
    assert [data for name, data in frames if name == "project"] == [
        {
            "slug": "digital-twin",
            "title": "Digital twin",
            "summary": "An agent that represents Adam.",
            "url": "https://x/projects/digital-twin",
        }
    ]


def test_error_turn_ends_with_done(make_runtime: Callable[..., Runtime]) -> None:
    frames = stream_events(make_runtime([ExplodingStream()]), [user("hi")])
    assert [name for name, _ in frames] == ["step", "step", "delta", "agent_error", "done"]
    assert frames[3][1]["code"] == "model_error"
    assert frames[4][1]["reply"] == "Part"


def test_history_reaches_the_model(make_runtime: Callable[..., Runtime]) -> None:
    runtime = make_runtime([text_stream("ok")])
    history = [user("a"), {"role": "assistant", "content": "b"}, user("c")]
    stream_events(runtime, history)
    sent = runtime.client.calls[0]["messages"]
    assert sent[1:] == history
    assert runtime.client.calls[0]["safety_identifier"]
