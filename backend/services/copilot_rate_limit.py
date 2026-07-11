"""In-memory sliding-window rate limits for Co-Pilot turns and tool calls."""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from typing import Callable, Literal


PricingTier = Literal["free", "pro", "premium"]


@dataclass(frozen=True)
class RateLimitRule:
    turns_per_minute: int
    tool_calls_per_hour: int


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0
    reason: str = ""
    limit: int = 0
    window_seconds: int = 0


DEFAULT_LIMITS: dict[PricingTier, RateLimitRule] = {
    "free": RateLimitRule(turns_per_minute=6, tool_calls_per_hour=10),
    "pro": RateLimitRule(turns_per_minute=18, tool_calls_per_hour=40),
    "premium": RateLimitRule(turns_per_minute=30, tool_calls_per_hour=80),
}


def _env_int(name: str, fallback: int) -> int:
    try:
        return max(1, int(os.getenv(name, fallback)))
    except (TypeError, ValueError):
        return fallback


def limits_for_tier(tier: str | None) -> RateLimitRule:
    normalized = (tier or "free").strip().lower()
    if normalized not in DEFAULT_LIMITS:
        normalized = "free"
    defaults = DEFAULT_LIMITS[normalized]  # type: ignore[index]
    prefix = normalized.upper()
    return RateLimitRule(
        turns_per_minute=_env_int(
            f"COPILOT_{prefix}_TURNS_PER_MINUTE",
            defaults.turns_per_minute,
        ),
        tool_calls_per_hour=_env_int(
            f"COPILOT_{prefix}_TOOL_CALLS_PER_HOUR",
            defaults.tool_calls_per_hour,
        ),
    )


class SlidingWindowRateLimiter:
    def __init__(self, now: Callable[[], float] | None = None):
        self._now = now or time.time
        self._turns: dict[str, deque[float]] = defaultdict(deque)
        self._tool_calls: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, events: deque[float], window_seconds: int, now: float) -> None:
        cutoff = now - window_seconds
        while events and events[0] <= cutoff:
            events.popleft()

    def check_turn(self, user_id: str, tier: str | None = None) -> RateLimitResult:
        rule = limits_for_tier(tier)
        return self._check(
            key=user_id,
            bucket=self._turns,
            limit=rule.turns_per_minute,
            window_seconds=60,
            reason="turns_per_minute",
        )

    def check_tool_calls(
        self,
        user_id: str,
        count: int,
        tier: str | None = None,
    ) -> RateLimitResult:
        if count <= 0:
            return RateLimitResult(allowed=True)
        rule = limits_for_tier(tier)
        return self._check(
            key=user_id,
            bucket=self._tool_calls,
            limit=rule.tool_calls_per_hour,
            window_seconds=3600,
            reason="tool_calls_per_hour",
            count=count,
        )

    def _check(
        self,
        *,
        key: str,
        bucket: dict[str, deque[float]],
        limit: int,
        window_seconds: int,
        reason: str,
        count: int = 1,
    ) -> RateLimitResult:
        now = self._now()
        with self._lock:
            events = bucket[key]
            self._prune(events, window_seconds, now)
            if len(events) + count > limit:
                retry_after = max(1, int(events[0] + window_seconds - now) + 1)
                return RateLimitResult(
                    allowed=False,
                    retry_after_seconds=retry_after,
                    reason=reason,
                    limit=limit,
                    window_seconds=window_seconds,
                )
            for _ in range(count):
                events.append(now)
        return RateLimitResult(allowed=True)

    def reset(self) -> None:
        with self._lock:
            self._turns.clear()
            self._tool_calls.clear()


copilot_rate_limiter = SlidingWindowRateLimiter()
