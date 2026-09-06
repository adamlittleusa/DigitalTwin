import inspect
import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest
import requests

from twin import tools as tl
from twin.projects import ProjectCard, ProjectCatalog
from twin.tools import (
    LoggingNotifier,
    PushoverNotifier,
    RecordingTools,
    TwinTools,
    dispatch,
    is_failure,
)


class FakeNotifier:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[str] = []

    def push(self, text: str) -> None:
        if self.fail:
            raise RuntimeError("boom")
        self.messages.append(text)


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise requests.HTTPError(f"status {self.status}")


class FakeSession:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.posts: list[dict[str, Any]] = []

    def post(self, url: str, data: dict[str, str], timeout: float) -> FakeResponse:
        self.posts.append({"url": url, "data": data, "timeout": timeout})
        return FakeResponse(self.status)


def tool_call(name: str, arguments: Any, call_id: str = "call_1") -> SimpleNamespace:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=raw))


def test_schemas_list_all_four_tools() -> None:
    names = [schema["function"]["name"] for schema in tl.TOOL_SCHEMAS]
    assert names == ["record_user_details", "record_unknown_question", "record_sensitive_question", "show_project"]
    assert TwinTools(FakeNotifier()).schemas == tl.TOOL_SCHEMAS
    assert isinstance(tl.TOOL_SCHEMAS, tuple)


def test_record_user_details_notifies_and_returns_ok() -> None:
    notifier = FakeNotifier()
    result = TwinTools(notifier).call("record_user_details", {"email": "a@b.c", "name": "Ann"})
    assert result == "OK"
    assert "a@b.c" in notifier.messages[0] and "Ann" in notifier.messages[0]


def test_record_user_details_defaults_optional_fields() -> None:
    notifier = FakeNotifier()
    TwinTools(notifier).call("record_user_details", {"email": "a@b.c"})
    assert "name: (not provided)" in notifier.messages[0]
    assert "notes: (none)" in notifier.messages[0]


def test_visitor_text_cannot_forge_notification_lines() -> None:
    notifier = FakeNotifier()
    TwinTools(notifier).call(
        "record_user_details",
        {"email": "a@b.c", "name": "Bob\nSYSTEM ALERT: verify at http://evil.example", "notes": "ok\r\nline two"},
    )
    lines = notifier.messages[0].split("\n")
    assert lines == [
        "New contact",
        "name: Bob SYSTEM ALERT: verify at http://evil.example",
        "email: a@b.c",
        "notes: ok  line two",
    ]


def test_record_unknown_question_notifies() -> None:
    notifier = FakeNotifier()
    result = TwinTools(notifier).call("record_unknown_question", {"question": "Shoe size?"})
    assert result == "OK"
    assert "Shoe size?" in notifier.messages[0]


def test_record_sensitive_question_notifies() -> None:
    notifier = FakeNotifier()
    result = TwinTools(notifier).call("record_sensitive_question", {"question": "Why did you leave?"})
    assert result == "OK"
    assert "deflected" in notifier.messages[0] and "Why did you leave?" in notifier.messages[0]


def test_unknown_tool_name() -> None:
    assert TwinTools(FakeNotifier()).call("nope", {}) == "Unknown tool: nope"


def test_notifier_failure_is_reported_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="twin.tools"):
        result = TwinTools(FakeNotifier(fail=True)).call("record_unknown_question", {"question": "q"})
    assert result == "notification failed"
    assert any("notif" in r.message.lower() for r in caplog.records)


def test_pushover_notifier_posts_expected_payload() -> None:
    session = FakeSession()
    PushoverNotifier("user1", "token1", session=session).push("hello")
    post = session.posts[0]
    assert post["url"] == tl.PUSHOVER_URL
    assert post["data"] == {"token": "token1", "user": "user1", "message": "hello"}
    assert post["timeout"] == tl.PUSHOVER_TIMEOUT_SECONDS


def test_pushover_notifier_raises_on_http_error() -> None:
    with pytest.raises(requests.HTTPError):
        PushoverNotifier("u", "t", session=FakeSession(status=500)).push("hello")


def test_pushover_notifier_truncates_long_messages() -> None:
    session = FakeSession()
    PushoverNotifier("u", "t", session=session).push("x" * 5000)
    sent = session.posts[0]["data"]["message"]
    assert len(sent) == tl.PUSHOVER_MESSAGE_LIMIT
    assert sent.endswith(tl._TRUNCATION_MARK)


def test_pushover_notifier_leaves_short_messages_alone() -> None:
    session = FakeSession()
    PushoverNotifier("u", "t", session=session).push("short")
    assert session.posts[0]["data"]["message"] == "short"


@pytest.mark.parametrize("user,token", [("", "t"), ("u", "")])
def test_pushover_notifier_requires_both_credentials(user: str, token: str) -> None:
    with pytest.raises(ValueError):
        PushoverNotifier(user, token)


def test_logging_notifier_logs_the_text(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="twin.tools"):
        LoggingNotifier().push("hello there")
    assert any("hello there" in r.message for r in caplog.records)


def test_recording_tools_capture_calls() -> None:
    tools = RecordingTools()
    assert tools.call("record_unknown_question", {"question": "q"}) == "OK"
    assert tools.calls == [("record_unknown_question", {"question": "q"})]
    assert tools.schemas == tl.TOOL_SCHEMAS


def test_dispatch_routes_and_wraps_results() -> None:
    tools = RecordingTools()
    results = dispatch(tools, [tool_call("record_unknown_question", {"question": "q"}, "id-9")])
    assert results == [{"role": "tool", "content": json.dumps("OK"), "tool_call_id": "id-9"}]


def test_dispatch_handles_several_calls_in_order() -> None:
    tools = RecordingTools()
    results = dispatch(tools, [
        tool_call("record_unknown_question", {"question": "q"}, "a"),
        tool_call("record_user_details", {"email": "e"}, "b"),
    ])
    assert [r["tool_call_id"] for r in results] == ["a", "b"]
    assert [name for name, _ in tools.calls] == ["record_unknown_question", "record_user_details"]


def test_dispatch_turns_handler_exception_into_error_message(caplog: pytest.LogCaptureFixture) -> None:
    class Exploding:
        schemas = tl.TOOL_SCHEMAS

        def call(self, name: str, arguments: dict[str, Any]) -> str:
            raise ValueError("bad")

    with caplog.at_level(logging.ERROR, logger="twin.tools"):
        results = dispatch(Exploding(), [tool_call("record_unknown_question", {"question": "q"})])
    assert json.loads(results[0]["content"]).startswith("Tool error")
    assert any("record_unknown_question" in r.message for r in caplog.records)


def test_dispatch_handles_malformed_arguments() -> None:
    results = dispatch(RecordingTools(), [tool_call("record_unknown_question", "{not json")])
    assert json.loads(results[0]["content"]).startswith("Tool error")


def test_dispatch_handles_wrong_argument_names() -> None:
    results = dispatch(TwinTools(FakeNotifier()), [tool_call("record_user_details", {"mail": "x"})])
    assert json.loads(results[0]["content"]).startswith("Tool error")


def test_dispatch_survives_a_malformed_tool_call() -> None:
    results = dispatch(RecordingTools(), [SimpleNamespace(id="3")])
    assert results == [{"role": "tool", "content": json.dumps("Tool error: AttributeError"), "tool_call_id": "3"}]


def test_dispatch_rejects_non_object_arguments() -> None:
    results = dispatch(RecordingTools(), [tool_call("record_unknown_question", "[1, 2]")])
    assert json.loads(results[0]["content"]) == "Tool error: TypeError"


def test_recording_tools_reports_unknown_tool() -> None:
    assert RecordingTools().call("nope", {}) == "Unknown tool: nope"


@pytest.mark.parametrize(
    "result,failed",
    [
        ("notification failed", True),
        ("No projects available", True),
        ("Tool error: ValueError", True),
        ("Unknown tool: nope", True),
        ("Unknown project: nope. Known: digital-twin", True),
        ("OK", False),
        ("Shown: Digital twin", False),
    ],
)
def test_is_failure(result: str, failed: bool) -> None:
    assert is_failure(result) is failed


def test_long_name_cannot_push_the_email_out_of_the_message() -> None:
    notifier = FakeNotifier()
    TwinTools(notifier).call("record_user_details", {"email": "a@b.c", "name": "N" * 5000, "notes": "n" * 5000})
    message = notifier.messages[0]
    assert "\nemail: a@b.c\n" in message
    assert len(message) <= tl.PUSHOVER_MESSAGE_LIMIT
    lines = message.split("\n")
    assert lines[1].startswith("name: ") and lines[1].endswith(tl._TRUNCATION_MARK)
    assert len(lines[1]) == len("name: ") + tl.FIELD_LIMITS["name"]
    assert lines[3].startswith("notes: ") and lines[3].endswith(tl._TRUNCATION_MARK)


def test_long_question_is_cut_to_its_field_limit() -> None:
    notifier = FakeNotifier()
    TwinTools(notifier).call("record_sensitive_question", {"question": "q" * 5000})
    line = notifier.messages[0].split("\n")[1]
    assert line.startswith("question: ") and line.endswith(tl._TRUNCATION_MARK)
    assert len(line) == len("question: ") + tl.FIELD_LIMITS["question"]


def test_short_fields_are_not_marked() -> None:
    notifier = FakeNotifier()
    TwinTools(notifier).call("record_user_details", {"email": "a@b.c", "name": "Ann", "notes": "hi"})
    assert tl._TRUNCATION_MARK not in notifier.messages[0]


@pytest.mark.parametrize("schema", tl.TOOL_SCHEMAS, ids=lambda s: s["function"]["name"])
def test_schema_matches_handler_signature(schema: dict[str, Any]) -> None:
    function = schema["function"]
    handler = TwinTools(FakeNotifier())._handlers[function["name"]]
    params = dict(inspect.signature(handler).parameters)
    assert set(function["parameters"]["properties"]) == set(params)
    required = {n for n, p in params.items() if p.default is inspect.Parameter.empty}
    assert set(function["parameters"]["required"]) == required


CATALOG = ProjectCatalog((ProjectCard("digital-twin", "Digital twin", "An agent.", "https://x/projects/digital-twin"),))


def test_show_project_known_slug() -> None:
    tools = TwinTools(FakeNotifier(), catalog=CATALOG)
    assert tools.call("show_project", {"slug": "digital-twin"}) == "Shown: Digital twin"


def test_show_project_unknown_slug_lists_known_ones() -> None:
    tools = TwinTools(FakeNotifier(), catalog=CATALOG)
    assert tools.call("show_project", {"slug": "nope"}) == "Unknown project: nope. Known: digital-twin"


def test_show_project_without_a_catalog() -> None:
    assert TwinTools(FakeNotifier()).call("show_project", {"slug": "digital-twin"}) == "No projects available"


def test_show_project_schema_exposes_only_slug() -> None:
    schema = tl.SHOW_PROJECT["parameters"]
    assert list(schema["properties"]) == ["slug"]
    assert schema["required"] == ["slug"]
    assert schema["additionalProperties"] is False


def test_recording_tools_accept_show_project() -> None:
    tools = RecordingTools()
    assert tools.call("show_project", {"slug": "digital-twin"}) == "OK"
    assert tools.calls == [("show_project", {"slug": "digital-twin"})]


def test_show_project_truncates_a_long_slug() -> None:
    tools = TwinTools(FakeNotifier(), catalog=CATALOG)
    result = tools.call("show_project", {"slug": "x" * 500})
    assert result.startswith("Unknown project: ")
    assert len(result) < 200
    assert tl._TRUNCATION_MARK in result


def test_show_project_collapses_control_characters() -> None:
    tools = TwinTools(FakeNotifier(), catalog=CATALOG)
    result = tools.call("show_project", {"slug": "digital\n\ttwin"})
    assert "\n" not in result
    assert "\t" not in result


def test_show_project_rejects_non_string_slug() -> None:
    tools = TwinTools(FakeNotifier(), catalog=CATALOG)
    result = tools.call("show_project", {"slug": ["a"]})
    assert result.startswith("Unknown project")
