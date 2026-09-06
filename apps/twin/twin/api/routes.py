"""The four routes."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import time
from collections.abc import AsyncIterator
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from fastapi import APIRouter, Request, Response
from sse_starlette import EventSourceResponse

from twin.api.schemas import RESTING_MESSAGE, ChatRequest, error_response
from twin.api.security import client_key, hash_key
from twin.api.sse import frame
from twin.api.stream import AgentStream
from twin.events import Delta, Done, Error
from twin.examples import EXAMPLE_QUESTIONS
from twin.wiring import Runtime, build_agent

log = logging.getLogger("twin.api")
router = APIRouter(prefix="/v1")
HEARTBEAT_SECONDS = 15
MAX_IN_FLIGHT = 8
BUSY_RETRY_SECONDS = 5
RATE_LIMITED_MESSAGE = "Too many messages in the last hour. Please wait a little."
BUSY_MESSAGE = "The twin is talking to as many people as it can right now. Try again in a moment."


def _version() -> str:
    try:
        return version("twin")
    except PackageNotFoundError:
        return "0"


def _runtime(request: Request) -> Runtime:
    return request.app.state.runtime


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    runtime = _runtime(request)
    return {
        "status": "ok",
        "knowledge_files": len(runtime.knowledge.files),
        "model": runtime.settings.model,
        "version": _version(),
    }


@router.get("/examples")
def examples() -> dict[str, list[str]]:
    return {"questions": list(EXAMPLE_QUESTIONS)}


@router.get("/projects")
def projects(request: Request) -> dict[str, list[dict[str, str]]]:
    return {"projects": [card.as_dict() for card in _runtime(request).catalog.cards]}


def _log_turn(
    request_id: str,
    body: ChatRequest,
    hashed: str,
    done: Done | None,
    first_delta_ms: int | None,
    started: float,
    outcome: str,
) -> None:
    """One JSON line per turn: ids, counts, timings, tokens, and the outcome. Never any message text."""
    log.info(
        json.dumps(
            {
                "request_id": request_id,
                "conversation_id": body.conversation_id,
                "client": hashed,
                "messages": len(body.messages),
                "rounds": done.rounds if done else None,
                "tools": list(done.tools) if done else [],
                "first_delta_ms": first_delta_ms,
                "total_ms": int((time.monotonic() - started) * 1000),
                "outcome": outcome,
                "usage": None if done is None or done.usage is None else dataclasses.asdict(done.usage),
            }
        )
    )


@router.post("/chat")
async def chat(request: Request, body: ChatRequest) -> Response:
    runtime = _runtime(request)
    settings = runtime.settings
    state = request.app.state
    request_id = getattr(request.state, "request_id", "")
    hashed = hash_key(client_key(request, settings), runtime.log_salt)

    if body.user_message_count > settings.max_user_messages:
        limit = settings.max_user_messages
        log.info(json.dumps({"request_id": request_id, "client": hashed, "outcome": "conversation_too_long"}))
        message = f"A conversation can hold at most {limit} of your messages. Start a new one."
        return error_response(413, "conversation_too_long", message)
    decision = runtime.limiter.allow(hashed)
    if not decision.allowed:
        log.info(json.dumps({"request_id": request_id, "client": hashed, "outcome": "rate_limited"}))
        retry = decision.retry_after
        headers = {"Retry-After": str(retry)}
        return error_response(429, "rate_limited", RATE_LIMITED_MESSAGE, headers=headers, retry_after=retry)
    if runtime.budget.remaining() <= 0:
        log.info(json.dumps({"request_id": request_id, "client": hashed, "outcome": "resting"}))
        return error_response(503, "resting", RESTING_MESSAGE)
    # Gate order is validation, conversation length, per-client limit, daily budget, busy: the per-client
    # token is spent before this check, so a visitor turned away for saturation still spends one of their own.
    if state.in_flight >= MAX_IN_FLIGHT:
        log.info(json.dumps({"request_id": request_id, "client": hashed, "outcome": "busy"}))
        return error_response(503, "busy", BUSY_MESSAGE, headers={"Retry-After": str(BUSY_RETRY_SECONDS)})

    state.in_flight += 1
    try:
        agent = build_agent(runtime, safety_identifier=hashed)
        history, message = body.history, body.message
        stream = AgentStream(lambda: agent.run(history, message))

        async def events() -> AsyncIterator[dict[str, str]]:
            started = time.monotonic()
            first_delta_ms: int | None = None
            outcome = "ok"
            done: Done | None = None
            try:
                async for event in stream:
                    if first_delta_ms is None and isinstance(event, Delta):
                        first_delta_ms = int((time.monotonic() - started) * 1000)
                    if isinstance(event, Error):
                        outcome = "error"
                    if isinstance(event, Done):
                        done = event
                    yield frame(event)
            except asyncio.CancelledError:  # sse-starlette cancels the stream when the visitor disconnects
                outcome = "disconnected"
                raise
            finally:
                # Only reached once the response below has been returned and the generator is iterated,
                # so this and the except below can never both fire for the same request.
                state.in_flight -= 1
                if done is None and outcome == "ok":  # the agent always ends with Done; none means the consumer left
                    outcome = "disconnected"
                _log_turn(request_id, body, hashed, done, first_delta_ms, started, outcome)

        return EventSourceResponse(events(), ping=HEARTBEAT_SECONDS, headers={"Cache-Control": "no-store"})
    except Exception:
        state.in_flight -= 1
        raise
