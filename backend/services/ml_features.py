"""Burnout-risk feature pipeline.

This module is ETL only. It builds flat, model-ready feature rows from existing
behavior logs and deliberately avoids training or scoring a model.
"""
from __future__ import annotations

import os
import statistics
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

MIN_OBSERVED_DAYS = 3


def _get_supabase() -> Client:
    return create_client(
        os.getenv("SUPABASE_URL", ""),
        os.getenv("SUPABASE_SERVICE_KEY", ""),
    )


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    else:
        raw = str(value).strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            try:
                dt = datetime.fromisoformat(raw[:10])
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _day_key(value: Any) -> date | None:
    dt = _parse_datetime(value)
    return dt.date() if dt else None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _stddev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return round(statistics.pstdev(values), 4)


def _slope(points: list[tuple[int, float]]) -> float | None:
    """Least-squares slope over observed day offsets, not zero-filled gaps."""
    if len(points) < MIN_OBSERVED_DAYS:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if not denominator:
        return None
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    return round(numerator / denominator, 4)


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _fetch_window_rows(
    db: Client,
    table: str,
    select_fields: str,
    user_id: str,
    timestamp_field: str,
    start_iso: str,
    end_iso: str,
) -> list[dict]:
    resp = (
        db.table(table)
        .select(select_fields)
        .eq("user_id", user_id)
        .gte(timestamp_field, start_iso)
        .lte(timestamp_field, end_iso)
        .order(timestamp_field)
        .execute()
    )
    return resp.data or []


def _fetch_session_rows(
    db: Client,
    user_id: str,
    start_iso: str,
    end_iso: str,
) -> list[dict]:
    """Fetch session rows touched in the window by either start or completion."""
    select_fields = "id, task_id, started_at, completed_at, was_rerouted"
    rows_by_key: dict[str, dict] = {}
    for timestamp_field in ("started_at", "completed_at"):
        rows = _fetch_window_rows(
            db,
            "session_logs",
            select_fields,
            user_id,
            timestamp_field,
            start_iso,
            end_iso,
        )
        for row in rows:
            key = str(row.get("id") or row.get("task_id") or (row.get("started_at"), row.get("completed_at")))
            rows_by_key[key] = row
    return list(rows_by_key.values())


def _daily_average(
    rows: list[dict],
    *,
    value_field: str,
    timestamp_field: str,
) -> dict[date, float]:
    buckets: dict[date, list[float]] = defaultdict(list)
    for row in rows:
        day = _day_key(row.get(timestamp_field))
        value = row.get(value_field)
        if day is None or value is None:
            continue
        try:
            buckets[day].append(float(value))
        except (TypeError, ValueError):
            continue
    return {day: sum(values) / len(values) for day, values in buckets.items() if values}


def _daily_points(daily_values: dict[date, float], start_date: date) -> list[tuple[int, float]]:
    return [
        ((day - start_date).days, value)
        for day, value in sorted(daily_values.items())
    ]


def build_user_feature_window(
    user_id: str,
    window_days: int = 14,
    *,
    db: Client | None = None,
    now: datetime | None = None,
) -> dict:
    """
    Build a flat burnout-risk feature row for one user over the last N days.

    Missing days are not zero-filled. Slope features are based only on observed
    daily averages and return None when there are fewer than three observed days.
    """
    if window_days < 1:
        raise ValueError("window_days must be >= 1")

    db = db or _get_supabase()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    end_dt = now
    start_dt = now - timedelta(days=window_days - 1)
    start_day = start_dt.date()
    start_iso = datetime.combine(start_day, time.min, tzinfo=timezone.utc).isoformat()
    end_iso = end_dt.isoformat()

    energy_rows = _fetch_window_rows(
        db,
        "energy_logs",
        "confirmed_score, confirmed_level, logged_at",
        user_id,
        "logged_at",
        start_iso,
        end_iso,
    )
    sleep_rows = _fetch_window_rows(
        db,
        "sleep_logs",
        "hours_slept, rested_score, logged_at",
        user_id,
        "logged_at",
        start_iso,
        end_iso,
    )
    routing_rows = _fetch_window_rows(
        db,
        "routing_logs",
        "was_rerouted, routed_at",
        user_id,
        "routed_at",
        start_iso,
        end_iso,
    )
    session_rows = _fetch_session_rows(db, user_id, start_iso, end_iso)

    energy_by_day = _daily_average(
        energy_rows, value_field="confirmed_score", timestamp_field="logged_at"
    )
    sleep_by_day = _daily_average(
        sleep_rows, value_field="hours_slept", timestamp_field="logged_at"
    )
    rested_by_day = _daily_average(
        sleep_rows, value_field="rested_score", timestamp_field="logged_at"
    )

    observed_days = set(energy_by_day) | set(sleep_by_day)
    for row in routing_rows:
        day = _day_key(row.get("routed_at"))
        if day:
            observed_days.add(day)
    for row in session_rows:
        day = _day_key(row.get("started_at") or row.get("completed_at"))
        if day:
            observed_days.add(day)

    data_coverage_days = len(observed_days)
    missing_days = max(0, window_days - data_coverage_days)

    if data_coverage_days < MIN_OBSERVED_DAYS:
        return {
            "user_id": user_id,
            "window_days": window_days,
            "window_start": start_day.isoformat(),
            "window_end": end_dt.date().isoformat(),
            "sufficient_data": False,
            "insufficient_data_reason": (
                f"Need at least {MIN_OBSERVED_DAYS} observed days across logs; "
                f"found {data_coverage_days}."
            ),
            "data_coverage_days": data_coverage_days,
            "missing_days": missing_days,
            "energy_log_count": len(energy_rows),
            "sleep_log_count": len(sleep_rows),
            "routing_log_count": len(routing_rows),
            "session_log_count": len(session_rows),
        }

    energy_values = [float(row["confirmed_score"]) for row in energy_rows if row.get("confirmed_score") is not None]
    sleep_values = [float(row["hours_slept"]) for row in sleep_rows if row.get("hours_slept") is not None]
    rested_values = [float(row["rested_score"]) for row in sleep_rows if row.get("rested_score") is not None]

    reroute_count = sum(1 for row in routing_rows if row.get("was_rerouted") is True)
    routing_total = len(routing_rows)

    sessions_with_signal = [
        row for row in session_rows if row.get("started_at") or row.get("completed_at")
    ]
    abandoned_sessions = [
        row for row in sessions_with_signal
        if row.get("started_at") and not row.get("completed_at")
    ]

    feature_row = {
        "user_id": user_id,
        "window_days": window_days,
        "window_start": start_day.isoformat(),
        "window_end": end_dt.date().isoformat(),
        "sufficient_data": True,
        "insufficient_data_reason": None,
        "data_coverage_days": data_coverage_days,
        "missing_days": missing_days,
        "energy_log_count": len(energy_rows),
        "sleep_log_count": len(sleep_rows),
        "routing_log_count": len(routing_rows),
        "session_log_count": len(session_rows),
        "energy_observed_days": len(energy_by_day),
        "sleep_observed_days": len(sleep_by_day),
        "avg_confirmed_energy": _mean(energy_values),
        "energy_trend_slope": _slope(_daily_points(energy_by_day, start_day)),
        "reroute_rate": _safe_rate(reroute_count, routing_total),
        "reroute_count": reroute_count,
        "routing_decision_count": routing_total,
        "task_abandonment_rate": _safe_rate(len(abandoned_sessions), len(sessions_with_signal)),
        "abandoned_session_count": len(abandoned_sessions),
        "session_signal_count": len(sessions_with_signal),
        "avg_hours_slept": _mean(sleep_values),
        "sleep_duration_trend_slope": _slope(_daily_points(sleep_by_day, start_day)),
        "sleep_duration_stddev": _stddev(sleep_values),
        "avg_rested_score": _mean(rested_values),
        "rested_score_trend_slope": _slope(_daily_points(rested_by_day, start_day)),
    }
    return feature_row
