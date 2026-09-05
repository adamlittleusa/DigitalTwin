"""Agent events projected onto what a visitor may see, as Server-Sent Event frames."""

from __future__ import annotations

import json
from typing import Any

from twin.events import AgentEvent, Delta, Done, Error, Project, Step, ToolCall, ToolResult


def frame(event: AgentEvent) -> dict[str, str]:
    """One SSE frame: the wire event name and a JSON payload with only visitor-safe fields."""
    name, data = _project(event)
    return {"event": name, "data": json.dumps(data)}


def _project(event: AgentEvent) -> tuple[str, dict[str, Any]]:
    if isinstance(event, Step):
        return "step", {"phase": event.phase, "round": event.round}
    if isinstance(event, ToolCall):
        return "tool", {"label": event.label}
    if isinstance(event, ToolResult):
        return "tool_result", {"ok": event.ok}
    if isinstance(event, Delta):
        return "delta", {"text": event.text}
    if isinstance(event, Project):
        return "project", {"slug": event.slug, "title": event.title, "summary": event.summary, "url": event.url}
    if isinstance(event, Done):
        return "done", {"reply": event.reply, "rounds": event.rounds}
    if isinstance(event, Error):
        return "agent_error", {"code": event.code, "message": event.message}
    raise TypeError(f"unknown event: {event!r}")
