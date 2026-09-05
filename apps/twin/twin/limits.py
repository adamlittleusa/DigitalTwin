"""In-memory limits: a per-visitor token bucket, a daily model-call budget, and a notification cap."""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

from twin.tools import Notifier

log = logging.getLogger(__name__)

SECONDS_PER_HOUR = 3600.0
_EPSILON = 1e-9  # absorbs float error in refill arithmetic so 180 s at 20/hour is exactly one token


class Clock(Protocol):
    """Seconds since the epoch, injectable so tests never sleep."""

    def now(self) -> float: ...


class SystemClock:
    def now(self) -> float:
        return time.time()


@dataclass(frozen=True)
class Decision:
    """The limiter's answer. retry_after is whole seconds: 0 when allowed, at least 1 when
    denied, 3600 when nothing refills."""

    allowed: bool
    retry_after: int


@dataclass(frozen=True)
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """A token bucket per key with capacity rate_per_hour + burst, refilling at rate_per_hour per hour."""

    def __init__(
        self, rate_per_hour: int, burst: int, clock: Clock, idle_seconds: float = 2 * SECONDS_PER_HOUR
    ) -> None:
        self._capacity = float(rate_per_hour + burst)
        self._refill_per_second = rate_per_hour / SECONDS_PER_HOUR
        self._clock = clock
        # A dropped bucket comes back full, so the idle window must be at least as long as a full
        # refill takes -- otherwise a visitor who waits it out earns more tokens than the rate allows.
        self._idle_seconds = (
            max(idle_seconds, self._capacity / self._refill_per_second)
            if self._refill_per_second > 0
            else idle_seconds
        )
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> Decision:
        with self._lock:
            now = self._clock.now()
            self._evict(now)
            current = self._buckets.get(key, _Bucket(tokens=self._capacity, updated=now))
            tokens = min(self._capacity, current.tokens + (now - current.updated) * self._refill_per_second)
            if tokens >= 1.0 - _EPSILON:
                self._buckets[key] = _Bucket(tokens=tokens - 1.0, updated=now)
                return Decision(allowed=True, retry_after=0)
            self._buckets[key] = _Bucket(tokens=tokens, updated=now)
            if self._refill_per_second <= 0:
                return Decision(allowed=False, retry_after=int(SECONDS_PER_HOUR))
            wait = (1.0 - tokens) / self._refill_per_second
            return Decision(allowed=False, retry_after=max(1, math.ceil(wait - _EPSILON)))

    def keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._buckets)

    def _evict(self, now: float) -> None:
        stale = [key for key, bucket in self._buckets.items() if now - bucket.updated > self._idle_seconds]
        for key in stale:
            del self._buckets[key]


class DailyBudget:
    """Counts model calls per UTC day. remaining() is for the request boundary; take() only records."""

    def __init__(self, limit: int, clock: Clock) -> None:
        self._limit = limit
        self._clock = clock
        self._lock = threading.Lock()
        self._day: date = self._today()
        self._count = 0

    def remaining(self) -> int:
        with self._lock:
            self._roll()
            return max(0, self._limit - self._count)

    def take(self) -> None:
        with self._lock:
            self._roll()
            self._count += 1

    def _today(self) -> date:
        return datetime.fromtimestamp(self._clock.now(), tz=UTC).date()

    def _roll(self) -> None:
        today = self._today()
        if today != self._day:
            self._day = today
            self._count = 0


class RateLimitedNotifier:
    """Forwards at most per_hour pushes in any rolling hour; the rest are logged so nothing is silently lost."""

    def __init__(self, inner: Notifier, per_hour: int, clock: Clock) -> None:
        self._inner = inner
        self._per_hour = per_hour
        self._clock = clock
        self._sent: deque[float] = deque()
        self._lock = threading.Lock()

    @property
    def inner(self) -> Notifier:
        return self._inner

    def push(self, text: str) -> None:
        with self._lock:
            now = self._clock.now()
            while self._sent and now - self._sent[0] >= SECONDS_PER_HOUR:
                self._sent.popleft()
            if len(self._sent) >= self._per_hour:
                log.warning("Notification withheld by the hourly cap: %s", text)
                return
            self._sent.append(now)
        self._inner.push(text)
