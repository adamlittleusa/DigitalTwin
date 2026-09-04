"""Eval cases: what the twin must and must not say, and the checks that decide it."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CATEGORIES: tuple[str, ...] = ("fact", "boundary", "unknown", "voice")


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    question: str
    must_include: tuple[str, ...] = ()
    must_not_include: tuple[str, ...] = ()
    expect_tool: str | None = None
    max_words: int | None = None


def load_cases(path: Path) -> tuple[EvalCase, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a list of cases")
    cases = tuple(_to_case(item, path) for item in raw)
    ids = [c.id for c in cases]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"{path}: duplicate case ids: {', '.join(duplicates)}")
    return cases


def check(case: EvalCase, reply: str, tool_calls: Sequence[str]) -> tuple[str, ...]:
    """Return every way the reply fails the case; empty means pass."""
    lowered = reply.lower()
    failures = [
        *(f"missing: {s!r}" for s in case.must_include if s.lower() not in lowered),
        *(f"forbidden: {s!r}" for s in case.must_not_include if s.lower() in lowered),
    ]
    if case.expect_tool and case.expect_tool not in tool_calls:
        failures.append(f"tool not called: {case.expect_tool}")
    if case.max_words is not None:
        words = len(reply.split())
        if words > case.max_words:
            failures.append(f"too long: {words} words, limit {case.max_words}")
    return tuple(failures)


def _to_case(item: Any, path: Path) -> EvalCase:
    if not isinstance(item, dict):
        raise ValueError(f"{path}: each case must be a mapping")
    for field in ("id", "category", "question"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(f"{path}: case {item.get('id', '?')!r} needs a non-empty {field}")
    if item["category"] not in CATEGORIES:
        raise ValueError(f"{path}: case {item['id']!r} has unknown category {item['category']!r}")
    return EvalCase(
        id=item["id"],
        category=item["category"],
        question=item["question"],
        must_include=_strings(item.get("must_include")),
        must_not_include=_strings(item.get("must_not_include")),
        expect_tool=item.get("expect_tool") or None,
        max_words=int(item["max_words"]) if item.get("max_words") is not None else None,
    )


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError("must_include and must_not_include must be lists of strings")
    return tuple(value)
