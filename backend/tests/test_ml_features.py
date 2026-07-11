from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.ml_features import build_user_feature_window


class FakeResult:
    def __init__(self, data: list[dict]):
        self.data = data


class FakeTable:
    def __init__(self, db: "FakeSupabase", name: str):
        self.db = db
        self.name = name
        self.filters: list[tuple[str, str, object]] = []
        self.order_field: str | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field: str, value: object):
        self.filters.append(("eq", field, value))
        return self

    def gte(self, field: str, value: object):
        self.filters.append(("gte", field, value))
        return self

    def lte(self, field: str, value: object):
        self.filters.append(("lte", field, value))
        return self

    def order(self, field: str, *_args, **_kwargs):
        self.order_field = field
        return self

    def execute(self):
        rows = list(self.db.tables.get(self.name, []))
        for op, field, value in self.filters:
            if op == "eq":
                rows = [row for row in rows if row.get(field) == value]
            elif op == "gte":
                rows = [row for row in rows if row.get(field) is not None and str(row.get(field)) >= str(value)]
            elif op == "lte":
                rows = [row for row in rows if row.get(field) is not None and str(row.get(field)) <= str(value)]
        if self.order_field:
            rows.sort(key=lambda row: str(row.get(self.order_field) or ""))
        return FakeResult([dict(row) for row in rows])


class FakeSupabase:
    def __init__(self, tables: dict[str, list[dict]]):
        self.tables = tables

    def table(self, name: str):
        return FakeTable(self, name)


def _iso(day: datetime) -> str:
    return day.isoformat()


def _db_for_days(days: list[datetime], user_id: str = "user-1") -> FakeSupabase:
    energy_logs = []
    sleep_logs = []
    routing_logs = []
    session_logs = []

    for idx, day in enumerate(days):
        energy_logs.append({
            "user_id": user_id,
            "confirmed_score": 8 - idx * 0.2,
            "confirmed_level": "balanced",
            "logged_at": _iso(day),
        })
        sleep_logs.append({
            "user_id": user_id,
            "hours_slept": 7.5 - idx * 0.05,
            "rested_score": 4,
            "logged_at": _iso(day),
        })
        for route_idx in range(2):
            routing_logs.append({
                "user_id": user_id,
                "was_rerouted": route_idx == 0 and idx % 2 == 0,
                "routed_at": _iso(day + timedelta(hours=route_idx)),
            })
        session_logs.append({
            "id": f"s-{idx}",
            "user_id": user_id,
            "task_id": f"t-{idx}",
            "started_at": _iso(day + timedelta(hours=3)),
            "completed_at": None if idx % 5 == 0 else _iso(day + timedelta(hours=4)),
            "was_rerouted": False,
        })

    return FakeSupabase({
        "energy_logs": energy_logs,
        "sleep_logs": sleep_logs,
        "routing_logs": routing_logs,
        "session_logs": session_logs,
    })


def test_feature_window_fully_populated_14_days():
    now = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)
    days = [
        datetime(2026, 7, 1 + i, 9, tzinfo=timezone.utc)
        for i in range(14)
    ]
    db = _db_for_days(days)

    row = build_user_feature_window("user-1", window_days=14, db=db, now=now)

    assert row["sufficient_data"] is True
    assert row["data_coverage_days"] == 14
    assert row["missing_days"] == 0
    assert row["energy_observed_days"] == 14
    assert row["avg_confirmed_energy"] == pytest.approx(6.7)
    assert row["energy_trend_slope"] == pytest.approx(-0.2)
    assert row["reroute_rate"] == pytest.approx(7 / 28)
    assert row["task_abandonment_rate"] == pytest.approx(0.2143)
    assert row["sleep_duration_trend_slope"] == pytest.approx(-0.05)
    assert row["sleep_duration_stddev"] is not None


def test_feature_window_sparse_days_does_not_zero_fill_trends():
    now = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)
    days = [
        datetime(2026, 7, 1, 9, tzinfo=timezone.utc),
        datetime(2026, 7, 4, 9, tzinfo=timezone.utc),
        datetime(2026, 7, 8, 9, tzinfo=timezone.utc),
        datetime(2026, 7, 11, 9, tzinfo=timezone.utc),
        datetime(2026, 7, 14, 9, tzinfo=timezone.utc),
    ]
    db = _db_for_days(days)

    row = build_user_feature_window("user-1", window_days=14, db=db, now=now)

    assert row["sufficient_data"] is True
    assert row["data_coverage_days"] == 5
    assert row["missing_days"] == 9
    assert row["energy_observed_days"] == 5
    assert row["energy_trend_slope"] == pytest.approx(-0.0604, abs=0.0001)
    assert row["sleep_duration_trend_slope"] == pytest.approx(-0.0151, abs=0.0001)


def test_feature_window_brand_new_user_returns_insufficient_data():
    now = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)
    days = [
        datetime(2026, 7, 13, 9, tzinfo=timezone.utc),
        datetime(2026, 7, 14, 9, tzinfo=timezone.utc),
    ]
    db = _db_for_days(days)

    row = build_user_feature_window("user-1", window_days=14, db=db, now=now)

    assert row["sufficient_data"] is False
    assert row["data_coverage_days"] == 2
    assert row["missing_days"] == 12
    assert "Need at least 3 observed days" in row["insufficient_data_reason"]
    assert "avg_confirmed_energy" not in row
