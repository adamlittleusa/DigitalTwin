import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from twin import agent as ag
from twin.agent import TwinAgent
from twin.config import Settings
from twin.tools import RecordingTools

SETTINGS = Settings(
    openai_api_key="sk-test", model="gpt-test", knowledge_dir=Path("k"),
    pushover_user=None, pushover_token=None,
)
PROMPT = "You are a test twin."


def text_response(content: str) -> SimpleNamespace:
    message = SimpleNamespace(role="assistant", content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=message)])


def tool_response(
    name: str, arguments: dict[str, Any], call_id: str = "call_1", finish_reason: str = "tool_calls"
) -> SimpleNamespace:
    call = SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))
    message = SimpleNamespace(role="assistant", content=None, tool_calls=[call])
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish_reason, message=message)])


def make_client(responses: list[SimpleNamespace]) -> tuple[Any, list[dict[str, Any]]]:
    queue = list(responses)
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> SimpleNamespace:
        calls.append(kwargs)
        return queue.pop(0)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, calls


def test_plain_reply_returns_text_and_sends_expected_messages() -> None:
    client, calls = make_client([text_response("Hello!")])
    tools = RecordingTools()
    reply = TwinAgent(client, SETTINGS, PROMPT, tools).reply(
        [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "before"}], "hi",
    )
    assert reply == "Hello!"
    sent = calls[0]
    assert sent["model"] == "gpt-test"
    assert sent["tools"] == tools.schemas
    assert sent["tool_choice"] == "auto"
    assert sent["messages"][0] == {"role": "system", "content": PROMPT}
    assert sent["messages"][1:3] == [
        {"role": "user", "content": "earlier"}, {"role": "assistant", "content": "before"},
    ]
    assert sent["messages"][-1] == {"role": "user", "content": "hi"}


def test_tool_call_is_dispatched_then_followed_up() -> None:
    first = tool_response("record_unknown_question", {"question": "q"}, "id-1")
    client, calls = make_client([first, text_response("I don't know that.")])
    tools = RecordingTools()
    reply = TwinAgent(client, SETTINGS, PROMPT, tools).reply([], "What is your shoe size?")
    assert reply == "I don't know that."
    assert tools.calls == [("record_unknown_question", {"question": "q"})]
    second_messages = calls[1]["messages"]
    assert second_messages[-2] is first.choices[0].message
    assert second_messages[-1] == {"role": "tool", "content": json.dumps("OK"), "tool_call_id": "id-1"}


def test_history_and_inputs_are_not_mutated() -> None:
    client, _ = make_client([tool_response("record_unknown_question", {"question": "q"}), text_response("ok")])
    history = [{"role": "user", "content": "earlier"}]
    TwinAgent(client, SETTINGS, PROMPT, RecordingTools()).reply(history, "hi")
    assert history == [{"role": "user", "content": "earlier"}]


def test_tool_round_cap_forces_a_final_text_reply() -> None:
    responses = [
        tool_response("record_unknown_question", {"question": f"q{i}"}, f"id-{i}") for i in range(ag.MAX_TOOL_ROUNDS)
    ]
    responses.append(text_response("Final answer."))
    client, calls = make_client(responses)
    reply = TwinAgent(client, SETTINGS, PROMPT, RecordingTools()).reply([], "loop")
    assert reply == "Final answer."
    assert len(calls) == ag.MAX_TOOL_ROUNDS + 1
    assert all(c["tool_choice"] == "auto" for c in calls[:-1])
    assert calls[-1]["tool_choice"] == "none"
    final_messages = calls[-1]["messages"]
    tool_messages = [m for m in final_messages if isinstance(m, dict) and m.get("role") == "tool"]
    assert tool_messages == [
        {"role": "tool", "content": json.dumps("OK"), "tool_call_id": f"id-{i}"} for i in range(ag.MAX_TOOL_ROUNDS)
    ]
    assert len(final_messages) == 2 + 2 * ag.MAX_TOOL_ROUNDS  # system + user + (assistant, tool) per round
    assert final_messages[0] == {"role": "system", "content": PROMPT}
    assert final_messages[1] == {"role": "user", "content": "loop"}


def test_empty_content_becomes_fallback() -> None:
    client, _ = make_client([text_response(None)])  # type: ignore[arg-type]
    assert TwinAgent(client, SETTINGS, PROMPT, RecordingTools()).reply([], "hi") == ag.FALLBACK_REPLY


def test_tool_calls_are_dispatched_even_when_finish_reason_is_stop() -> None:
    first = tool_response("record_unknown_question", {"question": "q"}, "id-1", finish_reason="stop")
    client, _ = make_client([first, text_response("Done.")])
    tools = RecordingTools()
    assert TwinAgent(client, SETTINGS, PROMPT, tools).reply([], "hi") == "Done."
    assert tools.calls == [("record_unknown_question", {"question": "q"})]


def test_final_turn_ignores_a_sneaked_tool_call() -> None:
    responses = [
        tool_response("record_unknown_question", {"question": f"q{i}"}, f"id-{i}") for i in range(ag.MAX_TOOL_ROUNDS)
    ]
    responses.append(tool_response("record_unknown_question", {"question": "extra"}, "id-extra"))
    client, calls = make_client(responses)
    tools = RecordingTools()
    reply = TwinAgent(client, SETTINGS, PROMPT, tools).reply([], "loop")
    assert reply == ag.FALLBACK_REPLY
    assert len(tools.calls) == ag.MAX_TOOL_ROUNDS
    assert calls[-1]["tool_choice"] == "none"


def test_empty_choices_returns_fallback(caplog: pytest.LogCaptureFixture) -> None:
    client, _ = make_client([SimpleNamespace(choices=[])])
    with caplog.at_level(logging.WARNING, logger="twin.agent"):
        reply = TwinAgent(client, SETTINGS, PROMPT, RecordingTools()).reply([], "hi")
    assert reply == ag.FALLBACK_REPLY
    assert any("no choices" in r.message for r in caplog.records)


def test_length_cutoff_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    cut = text_response("I worked at Corelight from")
    cut.choices[0].finish_reason = "length"
    client, _ = make_client([cut])
    with caplog.at_level(logging.WARNING, logger="twin.agent"):
        reply = TwinAgent(client, SETTINGS, PROMPT, RecordingTools()).reply([], "hi")
    assert reply == "I worked at Corelight from"
    assert any("cut off" in r.message for r in caplog.records)


def test_tool_rounds_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    client, _ = make_client([tool_response("record_unknown_question", {"question": "q"}), text_response("ok")])
    with caplog.at_level(logging.INFO, logger="twin.agent"):
        TwinAgent(client, SETTINGS, PROMPT, RecordingTools()).reply([], "hi")
    assert any("Tool round 1" in r.message and "record_unknown_question" in r.message for r in caplog.records)


def test_real_sdk_response_object_round_trips() -> None:
    from openai.types.chat import ChatCompletion

    real = ChatCompletion.model_validate(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-test",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "record_unknown_question",
                                    "arguments": json.dumps({"question": "q"}),
                                },
                            }
                        ],
                    },
                }
            ],
        }
    )
    client, calls = make_client([real, text_response("Handled.")])
    tools = RecordingTools()
    assert TwinAgent(client, SETTINGS, PROMPT, tools).reply([], "hi") == "Handled."
    assert tools.calls == [("record_unknown_question", {"question": "q"})]
    assert calls[1]["messages"][-2] is real.choices[0].message
