"""Fakes shared by the unit tests. Nothing here touches the network."""

from __future__ import annotations


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
