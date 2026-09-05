"""Fakes shared by the unit tests. Nothing here touches the network."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class FakeClock:
    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.t = start

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def push(self, text: str) -> None:
        self.messages.append(text)


def write_md(root: Path, rel: str, meta: dict[str, Any], body: str) -> None:
    """Write one knowledge file with YAML frontmatter under root."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body + "\n", encoding="utf-8")


def project_meta(title: str) -> dict[str, Any]:
    return {"title": title, "kind": "project", "period": "2026-09 to present", "public": True}


IDENTITY_META: dict[str, Any] = {"title": "Identity", "kind": "identity", "public": True}
