from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Address
from starlette.types import Receive, Scope, Send

from twin.api.app import create_app
from twin.api.routes import MAX_IN_FLIGHT
from twin.api.schemas import MAX_BODY_BYTES, MAX_MESSAGE_CHARS
from twin.api.security import RequestIdMiddleware, client_key
from twin.wiring import Runtime

JSON = {"Content-Type": "application/json"}
ORIGIN = "https://adambuilds.ai"


def client_for(runtime: Runtime, **kwargs: Any) -> TestClient:
    return TestClient(create_app(runtime), **kwargs)


@dataclass(frozen=True)
class FakeRequest:
    """Only the two attributes client_key reads, shaped like a Starlette request."""

    headers: Mapping[str, str]
    client: Address | None


def req(forwarded: str | None = None, peer: str | None = "10.0.0.1") -> FakeRequest:
    headers = {} if forwarded is None else {"x-forwarded-for": forwarded}
    return FakeRequest(headers, None if peer is None else Address(peer, 40000))


def user(content: str) -> dict[str, str]:
    return {"role": "user", "content": content}


def assistant(content: str) -> dict[str, str]:
    return {"role": "assistant", "content": content}


def test_health(make_runtime: Callable[..., Runtime]) -> None:
    response = client_for(make_runtime()).get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["knowledge_files"] == 2
    assert body["model"] == "gpt-5.4-mini"
    assert body["version"]
    assert response.headers["x-request-id"]


def test_examples(make_runtime: Callable[..., Runtime]) -> None:
    body = client_for(make_runtime()).get("/v1/examples").json()
    assert len(body["questions"]) == 4


def test_projects(make_runtime: Callable[..., Runtime]) -> None:
    body = client_for(make_runtime()).get("/v1/projects").json()
    assert body["projects"] == [
        {
            "slug": "digital-twin",
            "title": "Digital twin",
            "summary": "An agent that represents Adam.",
            "url": "https://x/projects/digital-twin",
        }
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"messages": []},
        {"messages": [assistant("hi")]},
        {"messages": [user("a"), user("b")]},
        {"messages": [user("a"), assistant("b")]},
        {"messages": [user("   ")]},
        {"messages": [user("x" * 2001)]},
        {"messages": [user("hi")], "conversation_id": "short"},
        {"messages": [user("hi")], "extra": 1},
        {"messages": [{"role": "system", "content": "hi"}]},
    ],
)
def test_invalid_requests_are_400_with_a_code(make_runtime: Callable[..., Runtime], payload: dict[str, Any]) -> None:
    response = client_for(make_runtime()).post("/v1/chat", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "invalid_request"
    assert "detail" in body


def test_surrounding_whitespace_does_not_count_toward_the_limit(make_runtime: Callable[..., Runtime]) -> None:
    padded = "  " + "x" * MAX_MESSAGE_CHARS + "  "
    with client_for(make_runtime()).stream("POST", "/v1/chat", json={"messages": [user(padded)]}) as response:
        assert response.status_code == 200
        response.read()


def test_malformed_json_is_400(make_runtime: Callable[..., Runtime]) -> None:
    response = client_for(make_runtime()).post("/v1/chat", content=b"{not json", headers=JSON)
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


def test_too_many_user_messages_is_413(make_runtime: Callable[..., Runtime]) -> None:
    messages: list[dict[str, str]] = []
    for i in range(3):
        messages += [user(f"q{i}"), assistant(f"a{i}")]
    messages.append(user("q3"))
    response = client_for(make_runtime(TWIN_MAX_USER_MESSAGES="3")).post("/v1/chat", json={"messages": messages})
    assert response.status_code == 413
    assert response.json()["code"] == "conversation_too_long"


def test_body_too_large_is_413(make_runtime: Callable[..., Runtime]) -> None:
    big = json.dumps({"messages": [user("x" * (MAX_BODY_BYTES + 10))]}).encode()
    response = client_for(make_runtime()).post("/v1/chat", content=big, headers=JSON)
    assert response.status_code == 413
    assert response.json()["code"] == "body_too_large"


def test_rate_limit_is_429_with_retry_after(make_runtime: Callable[..., Runtime]) -> None:
    client = client_for(make_runtime(TWIN_PER_CLIENT_HOURLY="1", TWIN_PER_CLIENT_BURST="1"))
    for _ in range(2):
        with client.stream("POST", "/v1/chat", json={"messages": [user("hi")]}) as response:
            assert response.status_code == 200
            response.read()
    response = client.post("/v1/chat", json={"messages": [user("hi")]})
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limited"
    assert int(response.headers["retry-after"]) >= 1


def test_daily_ceiling_is_503_before_any_model_call(make_runtime: Callable[..., Runtime]) -> None:
    runtime = make_runtime(TWIN_DAILY_CALL_LIMIT="1")
    client = client_for(runtime)
    with client.stream("POST", "/v1/chat", json={"messages": [user("hi")]}) as response:
        response.read()
    calls_before = len(runtime.client.calls)
    response = client.post("/v1/chat", json={"messages": [user("again")]})
    assert response.status_code == 503
    assert response.json()["code"] == "resting"
    assert len(runtime.client.calls) == calls_before


def test_cors_allows_only_configured_origins(make_runtime: Callable[..., Runtime]) -> None:
    client = client_for(make_runtime(TWIN_ALLOWED_ORIGINS="https://adambuilds.ai"))
    preflight = {"Access-Control-Request-Method": "POST"}
    allowed = client.options("/v1/chat", headers={"Origin": "https://adambuilds.ai", **preflight})
    assert allowed.headers.get("access-control-allow-origin") == "https://adambuilds.ai"
    denied = client.options("/v1/chat", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in denied.headers


def test_unexpected_exception_is_a_500_body(make_runtime: Callable[..., Runtime]) -> None:
    app = create_app(make_runtime())

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret detail")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert response.json() == {"code": "internal", "message": "Something went wrong on our side."}
    assert "secret detail" not in response.text


def test_error_responses_carry_request_id_and_cors(make_runtime: Callable[..., Runtime]) -> None:
    client = client_for(make_runtime(TWIN_ALLOWED_ORIGINS=ORIGIN))
    invalid = client.post("/v1/chat", json={"messages": []}, headers={"Origin": ORIGIN})
    assert invalid.status_code == 400
    assert invalid.headers["x-request-id"]
    assert invalid.headers["access-control-allow-origin"] == ORIGIN
    big = json.dumps({"messages": [user("x" * (MAX_BODY_BYTES + 10))]}).encode()
    oversized = client.post("/v1/chat", content=big, headers={**JSON, "Origin": ORIGIN})
    assert oversized.status_code == 413
    assert oversized.headers["x-request-id"]
    assert oversized.headers["access-control-allow-origin"] == ORIGIN


def test_request_id_is_stamped_even_when_the_app_sends_no_headers() -> None:
    async def bare(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 204})
        await send({"type": "http.response.body", "body": b""})

    response = TestClient(RequestIdMiddleware(bare)).get("/")
    assert response.status_code == 204
    assert response.headers["x-request-id"]


def test_busy_when_too_many_turns_in_flight(make_runtime: Callable[..., Runtime]) -> None:
    runtime = make_runtime()
    app = create_app(runtime)
    app.state.in_flight = MAX_IN_FLIGHT
    response = TestClient(app).post("/v1/chat", json={"messages": [user("hi")]})
    assert response.status_code == 503
    assert response.json()["code"] == "busy"
    assert response.headers["retry-after"] == "5"
    assert runtime.client.calls == []


def test_in_flight_returns_to_zero_after_a_turn(make_runtime: Callable[..., Runtime]) -> None:
    app = create_app(make_runtime())
    with TestClient(app).stream("POST", "/v1/chat", json={"messages": [user("hi")]}) as response:
        assert response.status_code == 200
        response.read()
    assert app.state.in_flight == 0


def test_in_flight_is_released_when_the_agent_cannot_be_built(
    make_runtime: Callable[..., Runtime], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("twin.api.routes.build_agent", boom)
    app = create_app(make_runtime())
    response = TestClient(app, raise_server_exceptions=False).post("/v1/chat", json={"messages": [user("hi")]})
    assert response.status_code == 500
    assert app.state.in_flight == 0


def test_client_key_uses_forwarded_header_only_when_trusted(make_runtime: Callable[..., Runtime]) -> None:
    trusted = make_runtime(TWIN_TRUST_PROXY="true", TWIN_LOG_SALT="s").settings
    untrusted = make_runtime().settings
    # The trusted proxy appends the address it actually saw last; anything before it is client-supplied.
    assert client_key(req("1.2.3.4, 203.0.113.9"), trusted) == "203.0.113.9"
    assert client_key(req("203.0.113.9"), untrusted) == "10.0.0.1"
    assert client_key(req(None), trusted) == "10.0.0.1"
    assert client_key(req(", 203.0.113.9"), trusted) == "203.0.113.9"
    assert client_key(req("203.0.113.9, "), trusted) == "203.0.113.9"
    assert client_key(req(" , "), trusted) == "10.0.0.1"


def test_client_key_is_unknown_without_a_peer_address(
    make_runtime: Callable[..., Runtime], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="twin.api"):
        assert client_key(req(peer=None), make_runtime().settings) == "unknown"
    assert any("rate-limit bucket" in r.getMessage() for r in caplog.records)
