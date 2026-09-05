import logging
import queue
import threading

import pytest

from tests.fakes import FakeClock, FakeNotifier
from twin.limits import DailyBudget, RateLimitedNotifier, RateLimiter


def test_bucket_capacity_is_rate_plus_burst() -> None:
    limiter = RateLimiter(rate_per_hour=20, burst=5, clock=FakeClock())
    decisions = [limiter.allow("a") for _ in range(26)]
    assert all(d.allowed for d in decisions[:25])
    assert decisions[25].allowed is False
    assert decisions[25].retry_after >= 1


def test_bucket_refills_at_the_hourly_rate() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rate_per_hour=20, burst=0, clock=clock)
    for _ in range(20):
        assert limiter.allow("a").allowed
    assert not limiter.allow("a").allowed
    clock.advance(180)  # one token every 3 minutes at 20 per hour
    assert limiter.allow("a").allowed
    assert not limiter.allow("a").allowed


def test_retry_after_counts_down_to_the_next_token() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rate_per_hour=60, burst=0, clock=clock)
    for _ in range(60):
        limiter.allow("a")
    assert limiter.allow("a").retry_after == 60
    clock.advance(30)
    assert limiter.allow("a").retry_after == 30


def test_keys_are_independent() -> None:
    limiter = RateLimiter(rate_per_hour=1, burst=0, clock=FakeClock())
    assert limiter.allow("a").allowed
    assert not limiter.allow("a").allowed
    assert limiter.allow("b").allowed


def test_idle_buckets_are_evicted() -> None:
    clock = FakeClock()
    # The requested idle_seconds=100 is floored at the full-refill time (3600 s here), so eviction
    # only happens once that much time has passed.
    limiter = RateLimiter(rate_per_hour=1, burst=0, clock=clock, idle_seconds=100)
    limiter.allow("a")
    clock.advance(3601)
    limiter.allow("b")
    assert "a" not in limiter.keys()
    assert "b" in limiter.keys()


def test_eviction_never_refills_faster_than_the_rate() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rate_per_hour=1, burst=5, clock=clock, idle_seconds=100)
    for _ in range(6):
        assert limiter.allow("a").allowed
    assert not limiter.allow("a").allowed
    clock.advance(7200)  # two hours earns exactly 2 tokens at 1 per hour
    assert limiter.allow("a").allowed
    assert limiter.allow("a").allowed
    assert not limiter.allow("a").allowed


def test_refill_is_capped_at_capacity() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rate_per_hour=20, burst=5, clock=clock)
    for _ in range(25):
        assert limiter.allow("a").allowed
    assert not limiter.allow("a").allowed
    clock.advance(36000)  # ten hours
    for _ in range(25):
        assert limiter.allow("a").allowed
    assert not limiter.allow("a").allowed


def test_allow_is_safe_across_threads() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rate_per_hour=20, burst=5, clock=clock)
    results: queue.Queue[bool] = queue.Queue()

    def worker() -> None:
        for _ in range(10):
            results.put(limiter.allow("a").allowed)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    decisions = []
    while not results.empty():
        decisions.append(results.get_nowait())
    assert len(decisions) == 80
    assert sum(decisions) == 25


def test_daily_budget_counts_and_rolls_over_at_utc_midnight() -> None:
    clock = FakeClock(start=1_800_000_000.0)  # 08:00 UTC on some day
    budget = DailyBudget(limit=2, clock=clock)
    assert budget.remaining() == 2
    budget.take()
    budget.take()
    assert budget.remaining() == 0
    budget.take()  # accounting only, never refuses
    assert budget.remaining() == 0
    clock.advance(24 * 3600)
    assert budget.remaining() == 2


def test_notifier_cap_forwards_then_logs(caplog: pytest.LogCaptureFixture) -> None:
    clock = FakeClock()
    inner = FakeNotifier()
    capped = RateLimitedNotifier(inner, per_hour=2, clock=clock)
    with caplog.at_level(logging.WARNING, logger="twin.limits"):
        capped.push("one")
        capped.push("two")
        capped.push("three")
    assert inner.messages == ["one", "two"]
    assert any("three" in r.message and "cap" in r.message.lower() for r in caplog.records)
    clock.advance(3601)
    capped.push("four")
    assert inner.messages == ["one", "two", "four"]
