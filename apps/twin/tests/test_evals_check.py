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


def test_all_failures_are_collected_in_order() -> None:
    c = case(must_include=("x",), must_not_include=("y",), expect_tool="t", max_words=1)
    assert check(c, "y y", []) == (
        "missing: 'x'",
        "forbidden: 'y'",
        "tool not called: t",
        "too long: 2 words, limit 1",
    )


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
    "id: a\n",                                                   # document is a mapping, not a list
    "- a string\n",                                              # item is not a mapping
    "- id: a\n  category: fact\n  question: Q?\n  must_include: x\n",   # scalar instead of list
    "- id: a\n  category: fact\n  question: Q?\n  must_includes: [x]\n", # unknown key
    "- id: a\n  category: fact\n  question: Q?\n  expect_tool: [t]\n",   # tool name not a string
    "- id: a\n  category: fact\n  question: Q?\n  max_words: abc\n",
    "- id: a\n  category: fact\n  question: Q?\n  max_words: true\n",
    "- id: a\n  category: fact\n  question: Q?\n  max_words: -1\n",
    "",                                                          # empty document
    "[]\n",                                                      # empty list
])
def test_load_cases_rejects_bad_input(tmp_path: Path, text: str) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(path)


def test_unknown_key_error_names_file_and_case(tmp_path: Path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text("- id: typo\n  category: fact\n  question: Q?\n  must_includes: [x]\n", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        load_cases(path)
    message = str(excinfo.value)
    assert "cases.yaml" in message and "typo" in message and "must_includes" in message


def test_missing_file_is_a_value_error_naming_the_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError) as excinfo:
        load_cases(tmp_path / "nope.yaml")
    assert "nope.yaml" in str(excinfo.value)


def test_invalid_yaml_is_a_value_error(tmp_path: Path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text("- id: [unclosed\n", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        load_cases(path)
    assert "invalid YAML" in str(excinfo.value)


def test_whole_word_matching_does_not_match_inside_words() -> None:
    c = case(category="voice", must_include_words=("AI",))
    assert check(c, "Shoot me an email.", []) == ("missing word: 'AI'",)
    assert check(c, "I'm an AI twin of Adam.", []) == ()
    assert check(c, "I'm an ai, yes.", []) == ()


def test_forbidden_words_match_whole_words_only() -> None:
    c = case(category="voice", must_not_include_words=("bot",))
    assert check(c, "I am not a robot.", []) == ()
    assert check(c, "I am a bot.", []) == ("forbidden word: 'bot'",)


def test_typographic_quotes_are_folded() -> None:
    c = case(category="voice", must_not_include=("i'm just an ai",))
    assert check(c, "I’m just an AI, but here goes.", []) == ("forbidden: \"i'm just an ai\"",)
    assert check(c, "I'm just an AI.", []) == ("forbidden: \"i'm just an ai\"",)


def test_forbid_tool_flags_an_unwanted_call() -> None:
    c = case(category="unknown", expect_tool="record_unknown_question", forbid_tool="record_sensitive_question")
    assert check(c, "No idea.", ["record_unknown_question"]) == ()
    assert check(c, "No idea.", ["record_unknown_question", "record_sensitive_question"]) == (
        "tool must not be called: record_sensitive_question",
    )


def test_expect_tool_passes_when_among_other_calls() -> None:
    c = case(category="unknown", expect_tool="record_unknown_question")
    assert check(c, "No idea.", ["record_user_details", "record_unknown_question"]) == ()


def test_tool_calls_as_a_string_is_rejected() -> None:
    with pytest.raises(TypeError):
        check(case(expect_tool="t"), "reply", "record_unknown_question")  # type: ignore[arg-type]


def test_load_cases_parses_new_fields(tmp_path: Path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(
        "- id: a\n  category: voice\n  question: Q?\n  must_include_words: [\"AI\"]\n"
        "  must_not_include_words: [\"bot\"]\n  forbid_tool: record_sensitive_question\n  max_words: 0\n",
        encoding="utf-8",
    )
    (c,) = load_cases(path)
    assert c.must_include_words == ("AI",)
    assert c.must_not_include_words == ("bot",)
    assert c.forbid_tool == "record_sensitive_question"
    assert c.max_words == 0
