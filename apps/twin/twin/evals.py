"""Eval cases: what the twin must and must not say, and the checks that decide it."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CATEGORIES: tuple[str, ...] = ("fact", "boundary", "unknown", "voice")
_ALLOWED_KEYS = frozenset(
    {
        "id",
        "category",
        "question",
        "must_include",
        "must_not_include",
        "must_include_words",
        "must_not_include_words",
        "expect_tool",
        "forbid_tool",
        "max_words",
    }
)
_QUOTE_FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


@dataclass(frozen=True)
class EvalCase:
    """One question and the conditions a reply must meet.

    Substring fields match case-insensitively anywhere in the reply; the `_words` variants
    match whole words only, which is what short tokens such as "AI" need.
    """

    id: str
    category: str
    question: str
    must_include: tuple[str, ...] = ()
    must_not_include: tuple[str, ...] = ()
    must_include_words: tuple[str, ...] = ()
    must_not_include_words: tuple[str, ...] = ()
    expect_tool: str | None = None
    forbid_tool: str | None = None
    max_words: int | None = None


def load_cases(path: Path) -> tuple[EvalCase, ...]:
    """Every case in the YAML file, validated. Raises ValueError naming the file and case for any problem."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{path}: cannot read eval file ({exc})") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML ({exc})") from exc
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{path}: expected a non-empty list of cases")
    cases = tuple(_to_case(item, path) for item in raw)
    ids = [c.id for c in cases]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"{path}: duplicate case ids: {', '.join(duplicates)}")
    return cases


def check(case: EvalCase, reply: str, tool_calls: Sequence[str]) -> tuple[str, ...]:
    """Return every way the reply fails the case; empty means pass."""
    if isinstance(tool_calls, str):
        raise TypeError("tool_calls must be a sequence of tool names, not a string")
    text = _normalise(reply)
    failures = [
        *(f"missing: {s!r}" for s in case.must_include if _normalise(s) not in text),
        *(f"forbidden: {s!r}" for s in case.must_not_include if _normalise(s) in text),
        *(f"missing word: {w!r}" for w in case.must_include_words if not _has_word(text, w)),
        *(f"forbidden word: {w!r}" for w in case.must_not_include_words if _has_word(text, w)),
    ]
    if case.expect_tool and case.expect_tool not in tool_calls:
        failures.append(f"tool not called: {case.expect_tool}")
    if case.forbid_tool and case.forbid_tool in tool_calls:
        failures.append(f"tool must not be called: {case.forbid_tool}")
    if case.max_words is not None:
        words = len(reply.split())
        if words > case.max_words:
            failures.append(f"too long: {words} words, limit {case.max_words}")
    return tuple(failures)


def _normalise(text: str) -> str:
    """Comparable form: Unicode-normalised, typographic quotes straightened, case-folded."""
    return unicodedata.normalize("NFKC", text).translate(_QUOTE_FOLD).casefold()


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(_normalise(word))}(?!\w)", text) is not None


def _to_case(item: Any, path: Path) -> EvalCase:
    if not isinstance(item, dict):
        raise ValueError(f"{path}: each case must be a mapping")
    label = f"{path}: case {item.get('id', '?')!r}"
    unknown = sorted(str(key) for key in set(item) - _ALLOWED_KEYS)
    if unknown:
        raise ValueError(f"{label} has unknown keys: {', '.join(unknown)}")
    for field in ("id", "category", "question"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(f"{label} needs a non-empty {field}")
    if item["category"] not in CATEGORIES:
        raise ValueError(f"{label} has unknown category {item['category']!r}")
    return EvalCase(
        id=item["id"],
        category=item["category"],
        question=item["question"],
        must_include=_strings(item, "must_include", label),
        must_not_include=_strings(item, "must_not_include", label),
        must_include_words=_strings(item, "must_include_words", label),
        must_not_include_words=_strings(item, "must_not_include_words", label),
        expect_tool=_optional_name(item, "expect_tool", label),
        forbid_tool=_optional_name(item, "forbid_tool", label),
        max_words=_optional_limit(item, "max_words", label),
    )


def _strings(item: dict[str, Any], key: str, label: str) -> tuple[str, ...]:
    value = item.get(key)
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ValueError(f"{label}: {key} must be a list of non-empty strings")
    return tuple(value)


def _optional_name(item: dict[str, Any], key: str, label: str) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: {key} must be a tool name")
    return value


def _optional_limit(item: dict[str, Any], key: str, label: str) -> int | None:
    value = item.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label}: {key} must be a non-negative integer")
    return value
