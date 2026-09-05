import json
import logging
from pathlib import Path
from typing import Any

import pytest

from tests.fakes import (
    ExplodingStream,
    FakeBudget,
    FakeNotifier,
    ScriptedClient,
    chunk,
    text_stream,
    tool_stream,
    usage_chunk,
)
from twin import agent as ag
from twin.agent import TwinAgent
from twin.config import Settings
from twin.events import Delta, Done, Error, Project, Step, ToolCall, ToolResult, Usage
from twin.projects import ProjectCard, ProjectCatalog
from twin.tools import RecordingTools, TwinTools

SETTINGS = Settings(
    openai_api_key="sk-test", model="gpt-test", knowledge_dir=Path("k"), pushover_user=None, pushover_token=None
)
PROMPT = "You are a test twin."
CATALOG = ProjectCatalog((ProjectCard("digital-twin", "Digital twin", "An agent.", "https://x/projects/digital-twin"),))
UNKNOWN = "record_unknown_question"


def events_of(client: Any, tools: Any = None, **kwargs: Any) -> list[Any]:
    agent = TwinAgent(client, SETTINGS, PROMPT, tools or RecordingTools(), **kwargs)
    return list(agent.run([], "hi"))


def kinds(events: list[Any]) -> list[str]:
    return [e.kind for e in events]


def capped_streams() -> list[Any]:
    return [tool_stream(UNKNOWN, {"question": f"q{i}"}, call_id=f"id-{i}") for i in range(ag.MAX_TOOL_ROUNDS)]


def test_plain_reply_streams_steps_deltas_and_done() -> None:
    client = ScriptedClient([text_stream("Hello there")])
    events = events_of(client)
    assert kinds(events) == ["step", "step", "delta", "delta", "done"]
    assert events[0] == Step("thinking", 1)
    assert events[1] == Step("composing", 1)
    assert "".join(e.text for e in events if isinstance(e, Delta)) == "Hello there"
    assert events[-1] == Done("Hello there", (), 1, Usage(100, 20, 50))
    sent = client.calls[0]
    assert sent["stream"] is True
    assert sent["stream_options"] == {"include_usage": True}
    assert sent["tool_choice"] == "auto"
    assert sent["messages"][0] == {"role": "system", "content": PROMPT}
    assert sent["messages"][-1] == {"role": "user", "content": "hi"}
    assert sent["timeout"] == SETTINGS.model_timeout_seconds
    assert "safety_identifier" not in sent and "prompt_cache_key" not in sent


def test_tool_round_then_text_keeps_interim_text() -> None:
    client = ScriptedClient([tool_stream(UNKNOWN, {"question": "q"}, leading_text="One sec. "), text_stream("Done.")])
    tools = RecordingTools()
    events = events_of(client, tools)
    assert kinds(events) == ["step", "step", "delta", "tool", "tool_result", "step", "delta", "delta", "done"]
    assert events[3] == ToolCall(UNKNOWN, "Passing this along to Adam")
    assert events[4] == ToolResult(UNKNOWN, True)
    assert events[5] == Step("thinking", 2)
    assert events[-1].reply == "One sec. Done."
    assert events[-1].tools == (UNKNOWN,)
    assert events[-1].rounds == 2
    assert tools.calls == [(UNKNOWN, {"question": "q"})]
    second = client.calls[1]["messages"]
    assert second[-2] == {
        "role": "assistant",
        "content": "One sec. ",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": UNKNOWN, "arguments": json.dumps({"question": "q"})},
            }
        ],
    }
    assert second[-1] == {"role": "tool", "content": json.dumps("OK"), "tool_call_id": "call_1"}


def test_show_project_emits_a_card_once() -> None:
    client = ScriptedClient(
        [
            tool_stream("show_project", {"slug": "digital-twin"}, call_id="a"),
            tool_stream("show_project", {"slug": "digital-twin"}, call_id="b"),
            text_stream("Here it is."),
        ]
    )
    events = events_of(client, RecordingTools(), catalog=CATALOG)
    projects = [e for e in events if isinstance(e, Project)]
    assert projects == [Project("digital-twin", "Digital twin", "An agent.", "https://x/projects/digital-twin")]


def test_show_project_unknown_slug_emits_nothing() -> None:
    client = ScriptedClient([tool_stream("show_project", {"slug": "nope"}), text_stream("Sorry.")])
    events = events_of(client, TwinTools(FakeNotifier(), catalog=CATALOG), catalog=CATALOG)
    assert not any(isinstance(e, Project) for e in events)
    assert ToolResult("show_project", False) in events


def test_show_project_without_a_catalog_is_not_ok() -> None:
    client = ScriptedClient([tool_stream("show_project", {"slug": "digital-twin"}), text_stream("Sorry.")])
    events = events_of(client, TwinTools(FakeNotifier()))
    assert not any(isinstance(e, Project) for e in events)
    assert ToolResult("show_project", False) in events


def test_real_tools_are_reached_through_fragments() -> None:
    notifier = FakeNotifier()
    client = ScriptedClient(
        [tool_stream("record_user_details", {"email": "a@b.c", "name": "Ann"}), text_stream("Saved.")]
    )
    events = events_of(client, TwinTools(notifier))
    assert ToolResult("record_user_details", True) in events
    assert "email: a@b.c" in notifier.messages[0]


def test_round_cap_forces_a_final_call_without_tools() -> None:
    client = ScriptedClient([*capped_streams(), text_stream("Final.")])
    events = events_of(client)
    assert client.calls[-1]["tool_choice"] == "none"
    assert events[-1].rounds == ag.MAX_TOOL_ROUNDS + 1
    assert events[-1].reply == "Final."
    thinking = [e for e in events if isinstance(e, Step) and e.phase == "thinking"]
    assert thinking[-1] == Step("thinking", ag.MAX_TOOL_ROUNDS + 1)


def test_sneaked_tool_call_on_the_final_turn_is_ignored() -> None:
    client = ScriptedClient([*capped_streams(), tool_stream(UNKNOWN, {"question": "extra"}, call_id="extra")])
    tools = RecordingTools()
    events = events_of(client, tools)
    assert len(tools.calls) == ag.MAX_TOOL_ROUNDS
    assert events[-1].reply == ag.FALLBACK_REPLY


def test_empty_content_becomes_fallback() -> None:
    events = events_of(ScriptedClient([[chunk(finish="stop")]]))
    assert events[-1] == Done(ag.FALLBACK_REPLY, (), 1, None)


def test_no_choices_at_all_is_fallback_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="twin.agent"):
        events = events_of(ScriptedClient([[usage_chunk()]]))
    assert events[-1].reply == ag.FALLBACK_REPLY
    assert any("no choices" in r.message for r in caplog.records)


def test_length_cutoff_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="twin.agent"):
        events = events_of(ScriptedClient([text_stream("I worked at", finish="length")]))
    assert events[-1].reply == "I worked at"
    assert any("cut off" in r.message for r in caplog.records)


def test_failure_before_the_first_chunk_yields_error_then_done() -> None:
    events = events_of(ScriptedClient([], raise_on_create=RuntimeError("auth")))
    assert kinds(events) == ["step", "error", "done"]
    assert events[1] == Error("model_error", ag.MODEL_ERROR_MESSAGE)
    assert events[2].reply == ag.FALLBACK_REPLY


def test_failure_mid_stream_keeps_partial_text() -> None:
    events = events_of(ScriptedClient([ExplodingStream()]))
    assert kinds(events) == ["step", "step", "delta", "error", "done"]
    assert events[-1].reply == "Part"


def test_reply_returns_done_text_and_never_raises() -> None:
    good = TwinAgent(ScriptedClient([text_stream("Yes.")]), SETTINGS, PROMPT, RecordingTools())
    assert good.reply([], "hi") == "Yes."
    bad = TwinAgent(ScriptedClient([], raise_on_create=RuntimeError("x")), SETTINGS, PROMPT, RecordingTools())
    assert bad.reply([], "hi") == ag.FALLBACK_REPLY


def test_identity_and_cache_keys_and_budget_are_used() -> None:
    budget = FakeBudget()
    client = ScriptedClient([tool_stream(UNKNOWN, {"question": "q"}), text_stream("ok")])
    events_of(client, safety_identifier="abc123", prompt_cache_key="twin-prompt-x", budget=budget)
    assert all(c["safety_identifier"] == "abc123" and c["prompt_cache_key"] == "twin-prompt-x" for c in client.calls)
    assert budget.taken == 2


def test_history_is_not_mutated() -> None:
    history = [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "before"}]
    TwinAgent(ScriptedClient([text_stream("ok")]), SETTINGS, PROMPT, RecordingTools()).reply(history, "hi")
    assert history == [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "before"}]


def test_tool_rounds_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="twin.agent"):
        events_of(ScriptedClient([tool_stream(UNKNOWN, {"question": "q"}), text_stream("ok")]))
    assert any("Tool round 1" in r.message and UNKNOWN in r.message for r in caplog.records)


def test_usage_is_summed_across_rounds() -> None:
    events = events_of(ScriptedClient([tool_stream(UNKNOWN, {"question": "q"}), text_stream("ok")]))
    assert events[-1].usage == Usage(200, 40, 100)
