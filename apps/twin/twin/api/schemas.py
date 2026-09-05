"""Request and error shapes for the API."""

from __future__ import annotations

from typing import Any, Literal

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_MESSAGE_CHARS = 2_000
MAX_TOTAL_CHARS = 24_000
MAX_MESSAGE_ITEMS = 64
MAX_BODY_BYTES = 32 * 1024
CONVERSATION_ID_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"
RESTING_MESSAGE = "The twin has used its budget for today and will be back tomorrow."


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)

    @field_validator("content")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be blank")
        return stripped


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = Field(default=None, pattern=CONVERSATION_ID_PATTERN)
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGE_ITEMS)

    @model_validator(mode="after")
    def _shape(self) -> ChatRequest:
        roles = [m.role for m in self.messages]
        if roles[0] != "user" or roles[-1] != "user":
            raise ValueError("messages must start and end with a user message")
        for earlier, later in zip(roles, roles[1:], strict=False):
            if earlier == later:
                raise ValueError("user and assistant messages must alternate")
        if sum(len(m.content) for m in self.messages) > MAX_TOTAL_CHARS:
            raise ValueError(f"messages must total at most {MAX_TOTAL_CHARS} characters")
        return self

    @property
    def user_message_count(self) -> int:
        return sum(1 for m in self.messages if m.role == "user")

    @property
    def history(self) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in self.messages[:-1]]

    @property
    def message(self) -> str:
        return self.messages[-1].content


def error_response(
    status: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message, **extra}
    return JSONResponse(status_code=status, content=body, headers=headers)
