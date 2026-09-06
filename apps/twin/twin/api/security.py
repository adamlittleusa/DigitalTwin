"""Who is calling, and two small ASGI middlewares: a body-size limit and a request id."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Mapping
from typing import Any, Protocol

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from twin.config import Settings

log = logging.getLogger("twin.api")


class RequestLike(Protocol):
    """The two things client_key reads. Read-only, so Starlette's Request and a plain fake both fit."""

    @property
    def headers(self) -> Mapping[str, str]: ...

    @property
    def client(self) -> Any: ...


def client_key(request: RequestLike, settings: Settings) -> str:
    """The visitor's address behind a trusted proxy, else the peer.

    Behind a trusted proxy the configured client-IP header (Fly sets Fly-Client-IP) wins when present.
    Otherwise the last non-empty X-Forwarded-For hop is used: a proxy appends the address it saw to the
    end, so anything earlier came from the client and can say whatever it likes. Without either, the
    peer address is used.
    """
    if settings.trust_proxy:
        header = settings.client_ip_header.lower()
        named = request.headers.get(header, "").strip() if header else ""
        if named:
            return named
        hops = [hop.strip() for hop in request.headers.get("x-forwarded-for", "").split(",")]
        appended = next((hop for hop in reversed(hops) if hop), None)
        if appended:
            return appended
    host = getattr(request.client, "host", None)
    if not host:
        log.warning("No client address on the request; such visitors share one rate-limit bucket.")
        return "unknown"
    return host


def hash_key(key: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{key}".encode()).hexdigest()[:16]


class _BodyTooLarge(Exception):
    """Raised from receive once the bytes actually delivered exceed the limit."""


class BodySizeLimitMiddleware:
    """Rejects requests whose body exceeds the limit, with the same 413 either way.

    A Content-Length above the limit is refused before the app sees the request. A body that declares nothing
    (chunked) is counted as it arrives: past the limit the app's receive raises _BodyTooLarge, and whatever the
    app then sends in reply is dropped in favour of the 413. The counter, not the exception, decides, because
    FastAPI turns any error raised while it reads the body into a 400 of its own, so the exception never reaches
    this middleware. Once the app has already started its response there is nothing left to replace.
    """

    def __init__(self, app: ASGIApp, limit: int) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = _content_length(scope)
        if declared is not None and declared > self.limit:
            await self._reject(send)
            return
        received = 0
        exceeded = False
        started = False

        async def counting_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.limit:
                    exceeded = True
                    raise _BodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if exceeded and not started:
                return  # the app is answering a body it never fully read; the 413 below replaces that answer
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except _BodyTooLarge:
            pass
        if not exceeded:
            return
        if started:
            log.warning("Request body passed %d bytes after the response had started; leaving it to end.", self.limit)
            return
        await self._reject(send)

    async def _reject(self, send: Send) -> None:
        message = f"The request body must be under {self.limit} bytes."
        await _send_json(send, 413, {"code": "body_too_large", "message": message})


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
                message.setdefault("headers", [])
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
