from __future__ import annotations

from services import context_builder


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, db: "FakeSupabase", name: str):
        self.db = db
        self.name = name
        self.filters: list[tuple[str, object]] = []
        self.desc = False
        self.row_limit: int | None = None
        self.single_row = False

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field: str, value: object):
        self.filters.append((field, value))
        return self

    def order(self, field: str, *_args, **kwargs):
        self.order_field = field
        self.desc = bool(kwargs.get("desc"))
        return self

    def limit(self, count: int):
        self.row_limit = count
        return self

    def single(self):
        self.single_row = True
        return self

    def execute(self):
        rows = list(self.db.tables.get(self.name, []))
        for field, value in self.filters:
            rows = [row for row in rows if row.get(field) == value]
        if getattr(self, "order_field", None):
            rows.sort(key=lambda row: str(row.get(self.order_field) or ""), reverse=self.desc)
        if self.row_limit is not None:
            rows = rows[: self.row_limit]
        if self.single_row:
            return FakeResult(rows[0] if rows else None)
        return FakeResult([dict(row) for row in rows])


class FakeSupabase:
    def __init__(self, burnout_rows: list[dict]):
        self.tables = {
            "profiles": [
                {
                    "id": "user-1",
                    "name": "Nini",
                    "google_calendar_connected": False,
                }
            ],
            "user_integrations": [],
            "energy_logs": [],
            "burnout_scores": burnout_rows,
        }

    def table(self, name: str):
        return FakeTable(self, name)


def _context_for(burnout_rows: list[dict]) -> str:
    return context_builder.build_context_for_user(
        FakeSupabase(burnout_rows),
        "user-1",
    )


def test_burnout_risk_block_appears_only_for_available_or_insufficient_score():
    no_score_context = _context_for([])
    assert "<burnout_risk>" not in no_score_context

    score_context = _context_for([
        {
            "user_id": "user-1",
            "score": 0.73,
            "label": True,
            "model_version": "burnout_logreg_v0.1",
            "features": {"sufficient_data": True},
            "computed_at": "2026-07-11T08:00:00",
        }
    ])
    assert "<burnout_risk>" in score_context
    assert "score: 0.73" in score_context
    assert "risk_band: high" in score_context

    insufficient_context = _context_for([
        {
            "user_id": "user-1",
            "score": 0.0,
            "label": False,
            "model_version": "burnout_logreg_v0.1",
            "features": {
                "sufficient_data": False,
                "insufficient_data_reason": "Need at least 3 observed days across logs; found 1.",
            },
            "computed_at": "2026-07-11T08:00:00",
        }
    ])
    assert "<burnout_risk>" in insufficient_context
    assert "status: insufficient_data" in insufficient_context
    assert "risk_band: insufficient_data" in insufficient_context
    assert "score: 0.0" not in insufficient_context
