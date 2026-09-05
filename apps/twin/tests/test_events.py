import dataclasses

import pytest

from twin import events as ev


def test_every_event_is_frozen_and_carries_its_kind() -> None:
    samples = [
        ev.Step("thinking", 1),
        ev.ToolCall("record_unknown_question", "Passing this along to Adam"),
        ev.ToolResult("record_unknown_question", True),
        ev.Delta("hi"),
        ev.Project("digital-twin", "Digital twin", "An agent.", "https://adambuilds.ai/projects/digital-twin"),
        ev.Done("hi", ("record_unknown_question",), 2, None),
        ev.Error("model_error", "boom"),
    ]
    assert [s.kind for s in samples] == ["step", "tool", "tool_result", "delta", "project", "done", "error"]
    for sample in samples:
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample.kind = "other"  # type: ignore[misc]


def test_usage_adds() -> None:
    total = ev.Usage(10, 5, 8) + ev.Usage(1, 2, 3)
    assert total == ev.Usage(11, 7, 11)


def test_labels_hide_the_difference_between_unknown_and_sensitive() -> None:
    assert ev.label_for("record_unknown_question") == ev.label_for("record_sensitive_question")
    assert ev.label_for("record_user_details") == "Saving your email for Adam"
    assert ev.label_for("show_project") == "Pulling up a project"
    assert ev.label_for("something_else") == "Working on it"
