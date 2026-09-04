"""The twin's tools: schemas the model sees, handlers, notifiers, and dispatch."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Iterable
from typing import Any, Final, Protocol

import requests

log = logging.getLogger(__name__)

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
PUSHOVER_TIMEOUT_SECONDS = 10.0
PUSHOVER_MESSAGE_LIMIT = 1024
_TRUNCATION_MARK = "…"

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f\u2028\u2029\u202a-\u202e\u2066-\u2069]")


def _truncate(text: str, limit: int = PUSHOVER_MESSAGE_LIMIT) -> str:
    """Text cut to the limit with a trailing mark, so a long message is delivered short rather than rejected."""
    if len(text) <= limit:
        return text
    return text[: limit - len(_TRUNCATION_MARK)] + _TRUNCATION_MARK


def _clean(value: object) -> str:
    """Visitor-supplied text made safe for one notification field: control characters and line breaks become spaces."""
    return _CONTROL_CHARS.sub(" ", str(value)).strip()


FIELD_LIMITS: Final[dict[str, int]] = {"name": 120, "email": 254, "notes": 500, "question": 600}


def _field(value: object, limit: int) -> str:
    """A visitor-supplied value cleaned and cut to its field limit, so every labelled line fits the message cap."""
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[: limit - len(_TRUNCATION_MARK)] + _TRUNCATION_MARK


RECORD_USER_DETAILS: dict[str, Any] = {
    "name": "record_user_details",
    "description": "Use this tool to record that a visitor wants to be in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "The visitor's email address"},
            "name": {"type": "string", "description": "The visitor's name, if they gave it"},
            "notes": {
                "type": "string",
                "description": "Anything from the conversation worth recording as context for the follow-up",
            },
        },
        "required": ["email"],
        "additionalProperties": False,
    },
}

RECORD_UNKNOWN_QUESTION: dict[str, Any] = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that could not be answered from what you know",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question that could not be answered"},
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}

RECORD_SENSITIVE_QUESTION: dict[str, Any] = {
    "name": "record_sensitive_question",
    "description": (
        "Use this tool whenever you deflect a question because a boundary says Adam handles "
        "that topic himself, so that he is notified"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question that was deflected"},
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}

TOOL_SCHEMAS: Final[tuple[dict[str, Any], ...]] = (
    {"type": "function", "function": RECORD_USER_DETAILS},
    {"type": "function", "function": RECORD_UNKNOWN_QUESTION},
    {"type": "function", "function": RECORD_SENSITIVE_QUESTION},
)


class Notifier(Protocol):
    def push(self, text: str) -> None: ...


class PushoverNotifier:
    """Sends a push notification through Pushover. Raises on HTTP failure."""

    def __init__(self, user: str, token: str, session: Any | None = None) -> None:
        if not user or not token:
            raise ValueError("PushoverNotifier needs both a user key and an app token")
        self._user = user
        self._token = token
        self._session = session if session is not None else requests.Session()

    def push(self, text: str) -> None:
        response = self._session.post(
            PUSHOVER_URL,
            data={"token": self._token, "user": self._user, "message": _truncate(text)},
            timeout=PUSHOVER_TIMEOUT_SECONDS,
        )
        response.raise_for_status()


class LoggingNotifier:
    """Fallback when Pushover is not configured: the notification goes to the log."""

    def push(self, text: str) -> None:
        log.info("NOTIFICATION: %s", text)


class ToolRegistry(Protocol):
    @property
    def schemas(self) -> tuple[dict[str, Any], ...]: ...

    def call(self, name: str, arguments: dict[str, Any]) -> str: ...


class TwinTools:
    """The real tool handlers, reporting through whichever Notifier they are given."""

    def __init__(self, notifier: Notifier) -> None:
        self._notifier = notifier
        self._handlers: dict[str, Callable[..., str]] = {
            "record_user_details": self.record_user_details,
            "record_unknown_question": self.record_unknown_question,
            "record_sensitive_question": self.record_sensitive_question,
        }

    @property
    def schemas(self) -> tuple[dict[str, Any], ...]:
        return TOOL_SCHEMAS

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        handler = self._handlers.get(name)
        if handler is None:
            return f"Unknown tool: {name}"
        return handler(**arguments)

    def record_user_details(self, email: str, name: str = "", notes: str = "") -> str:
        return self._notify(
            "New contact\n"
            f"name: {_field(name, FIELD_LIMITS['name']) or '(not provided)'}\n"
            f"email: {_field(email, FIELD_LIMITS['email'])}\n"
            f"notes: {_field(notes, FIELD_LIMITS['notes']) or '(none)'}"
        )

    def record_unknown_question(self, question: str) -> str:
        return self._notify(f"Question I couldn't answer\nquestion: {_field(question, FIELD_LIMITS['question'])}")

    def record_sensitive_question(self, question: str) -> str:
        return self._notify(f"Sensitive question deflected\nquestion: {_field(question, FIELD_LIMITS['question'])}")

    def _notify(self, text: str) -> str:
        try:
            self._notifier.push(text)
        except Exception:
            log.exception("Notification failed for: %s", text)
            return "notification failed"
        return "OK"


_KNOWN_TOOL_NAMES = frozenset(schema["function"]["name"] for schema in TOOL_SCHEMAS)


class RecordingTools:
    """Test double: records every call and never contacts anything."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    @property
    def schemas(self) -> tuple[dict[str, Any], ...]:
        return TOOL_SCHEMAS

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        if name not in _KNOWN_TOOL_NAMES:
            return f"Unknown tool: {name}"
        return "OK"


def dispatch(tools: ToolRegistry, tool_calls: Iterable[Any]) -> list[dict[str, Any]]:
    """Run each tool call the model asked for and return the tool messages to send back."""
    return [_run_one(tools, call) for call in tool_calls]


def _run_one(tools: ToolRegistry, call: Any) -> dict[str, Any]:
    call_id = getattr(call, "id", None) or ""
    name = "<unknown>"
    raw_arguments: Any = None
    try:
        name = call.function.name
        raw_arguments = call.function.arguments
        arguments = json.loads(raw_arguments or "{}")
        if not isinstance(arguments, dict):
            raise TypeError("tool arguments must be a JSON object")
        result = tools.call(name, arguments)
    except Exception as exc:
        log.exception("Tool %s failed with arguments %r", name, raw_arguments)
        result = f"Tool error: {type(exc).__name__}"
    return {"role": "tool", "content": json.dumps(result), "tool_call_id": call_id}
