from pathlib import Path

import pytest

from twin.evals import EvalCase, check, load_cases


def case(**overrides: object) -> EvalCase:
    base = dict(id="c", category="fact", question="Q?")
    return EvalCase(**{**base, **overrides})  # type: ignore[arg-type]


def test_passing_fact_case_has_no_failures() -> None:
    assert check(case(must_include=("2018", "2022")), "From 2018 to 2022.", []) == ()


def test_must_include_is_case_insensitive() -> None:
    assert check(case(must_include=("recorded future",)), "At Recorded Future.", []) == ()


def test_missing_substring_is_reported() -> None:
    failures = check(case(must_include=("2018", "2022")), "From 2018.", [])
    assert failures == ("missing: '2022'",)


def test_forbidden_substring_is_reported() -> None:
    failures = check(case(must_not_include=("as an ai language model",)), "As an AI language model, I...", [])
    assert failures == ("forbidden: 'as an ai language model'",)


def test_expected_tool_must_be_called() -> None:
    c = case(category="unknown", expect_tool="record_unknown_question")
    assert check(c, "No idea.", ["record_unknown_question"]) == ()
    assert check(c, "No idea.", []) == ("tool not called: record_unknown_question",)


def test_max_words_is_enforced() -> None:
    c = case(category="voice", max_words=3)
    assert check(c, "one two three", []) == ()
    assert check(c, "one two three four", []) == ("too long: 4 words, limit 3",)


def test_all_failures_are_collected() -> None:
    c = case(must_include=("x",), must_not_include=("y",), expect_tool="t", max_words=1)
    failures = check(c, "y y", [])
    assert len(failures) == 4


def test_load_cases_parses_yaml(tmp_path: Path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(
        "- id: a\n  category: fact\n  question: Q?\n  must_include: [\"x\"]\n"
        "- id: b\n  category: unknown\n  question: R?\n  expect_tool: record_unknown_question\n  max_words: 50\n",
        encoding="utf-8",
    )
    cases = load_cases(path)
    assert [c.id for c in cases] == ["a", "b"]
    assert cases[0].must_include == ("x",)
    assert cases[0].must_not_include == ()
    assert cases[1].expect_tool == "record_unknown_question"
    assert cases[1].max_words == 50


@pytest.mark.parametrize("text", [
    "- category: fact\n  question: Q?\n",
    "- id: a\n  category: weird\n  question: Q?\n",
    "- id: a\n  category: fact\n",
    "- id: a\n  category: fact\n  question: Q?\n- id: a\n  category: fact\n  question: R?\n",
])
def test_load_cases_rejects_bad_input(tmp_path: Path, text: str) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(path)
