"""Who is calling, and two small ASGI middlewares: a body-size limit and a request id."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from twin.config import Settings


def client_key(request: Any, settings: Settings) -> str:
    """The visitor's address: the first X-Forwarded-For hop when a proxy is trusted, else the peer."""
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    client = getattr(request, "client", None)
    return getattr(client, "host", None) or "unknown"


def hash_key(key: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{key}".encode()).hexdigest()[:16]


class BodySizeLimitMiddleware:
    """Rejects requests whose declared body exceeds the limit before any parsing."""

    def __init__(self, app: ASGIApp, limit: int) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            declared = _content_length(scope)
            if declared is not None and declared > self.limit:
                message = f"The request body must be under {self.limit} bytes."
                await _send_json(send, 413, {"code": "body_too_large", "message": message})
                return
        await self.app(scope, receive, send)


class RequestIdMiddleware:
    """Stamps every request with an id, exposed as request.state.request_id and the X-Request-Id header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-Id"] = request_id
            await send(message)

        await self.app(scope, receive, send_with_id)


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _send_json(send: Send, status: int, body: dict[str, Any]) -> None:
    payload = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": payload})
