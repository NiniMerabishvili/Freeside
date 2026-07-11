from __future__ import annotations

from services.copilot_rate_limit import SlidingWindowRateLimiter


def test_turn_limit_triggers_and_resets_after_window(monkeypatch):
    monkeypatch.setenv("COPILOT_FREE_TURNS_PER_MINUTE", "2")
    now = 1_000.0
    limiter = SlidingWindowRateLimiter(now=lambda: now)

    assert limiter.check_turn("u1", "free").allowed is True
    assert limiter.check_turn("u1", "free").allowed is True

    limited = limiter.check_turn("u1", "free")
    assert limited.allowed is False
    assert limited.reason == "turns_per_minute"
    assert limited.retry_after_seconds > 0

    now += 61
    assert limiter.check_turn("u1", "free").allowed is True


def test_tool_call_limit_triggers_and_resets_after_window(monkeypatch):
    monkeypatch.setenv("COPILOT_FREE_TOOL_CALLS_PER_HOUR", "2")
    now = 2_000.0
    limiter = SlidingWindowRateLimiter(now=lambda: now)

    assert limiter.check_tool_calls("u1", 2, "free").allowed is True

    limited = limiter.check_tool_calls("u1", 1, "free")
    assert limited.allowed is False
    assert limited.reason == "tool_calls_per_hour"
    assert limited.retry_after_seconds > 0

    now += 3601
    assert limiter.check_tool_calls("u1", 1, "free").allowed is True
