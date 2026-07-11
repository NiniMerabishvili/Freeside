from __future__ import annotations

from services.energy_calibration import apply_energy_bias, energy_bias_for_user


class FakeResult:
    def __init__(self, data: list[dict]):
        self.data = data


class FakeTable:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field: str, value: object):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, count: int):
        self.rows = self.rows[:count]
        return self

    def execute(self):
        return FakeResult(self.rows)


class FakeSupabase:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def table(self, name: str):
        assert name == "energy_logs"
        return FakeTable(list(self.rows))


def test_energy_bias_converges_to_consistent_offset():
    rows = [
        {
            "user_id": "u1",
            "ai_suggested_score": 4,
            "confirmed_score": 6,
            "logged_at": f"2026-07-{10 + i:02d}T08:00:00",
        }
        for i in range(8)
    ]
    db = FakeSupabase(rows)

    bias = energy_bias_for_user(db, "u1", limit=30)
    adjusted = apply_energy_bias(
        {"suggested_score": 5, "suggested_level": "balanced", "reasoning": "Moderate day."},
        bias,
    )

    assert bias == 2.0
    assert adjusted["raw_suggested_score"] == 5
    assert adjusted["suggested_score"] == 7
    assert adjusted["suggested_level"] == "high"
