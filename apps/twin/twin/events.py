"""The events a turn of the agent produces, in the order it produces them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.prompt_tokens + other.prompt_tokens,
            self.completion_tokens + other.completion_tokens,
            self.cached_tokens + other.cached_tokens,
        )


@dataclass(frozen=True)
class Step:
    phase: Literal["thinking", "composing"]
    round: int
    kind: Literal["step"] = "step"


@dataclass(frozen=True)
class ToolCall:
    name: str
    label: str
    kind: Literal["tool"] = "tool"


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    kind: Literal["tool_result"] = "tool_result"


@dataclass(frozen=True)
class Delta:
    text: str
    kind: Literal["delta"] = "delta"


@dataclass(frozen=True)
class Project:
    slug: str
    title: str
    summary: str
    url: str
    kind: Literal["project"] = "project"


@dataclass(frozen=True)
class Done:
    reply: str
    tools: tuple[str, ...]
    rounds: int
    usage: Usage | None = None
    kind: Literal["done"] = "done"


@dataclass(frozen=True)
class Error:
    code: str
    message: str
    kind: Literal["error"] = "error"


AgentEvent = Step | ToolCall | ToolResult | Delta | Project | Done | Error

TOOL_LABELS: Final[dict[str, str]] = {
    "record_user_details": "Saving your email for Adam",
    "record_unknown_question": "Passing this along to Adam",
    "record_sensitive_question": "Passing this along to Adam",
    "show_project": "Pulling up a project",
}
DEFAULT_LABEL: Final = "Working on it"


def label_for(tool_name: str) -> str:
    """The visitor-facing label for a tool. The two notification tools share one so a deflection is not visible."""
    return TOOL_LABELS.get(tool_name, DEFAULT_LABEL)
