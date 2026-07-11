from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeResult:
    def __init__(self, data: list[dict] | None = None):
        self.data = data or []


class FakeTable:
    def __init__(self, db: "FakeSupabase", name: str):
        self.db = db
        self.name = name
        self.filters: list[tuple[str, Any]] = []
        self.update_payload: dict | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field: str, value: Any):
        self.filters.append((field, value))
        return self

    def update(self, payload: dict):
        self.update_payload = payload
        return self

    def execute(self):
        rows = self.db.tables.get(self.name, [])
        for field, value in self.filters:
            rows = [row for row in rows if row.get(field) == value]
        if self.update_payload is not None:
            for row in rows:
                row.update(self.update_payload)
            return FakeResult(rows)
        return FakeResult([dict(row) for row in rows])


class FakeSupabase:
    def __init__(self, tables: dict[str, list[dict]]):
        self.tables = tables

    def table(self, name: str):
        return FakeTable(self, name)


@pytest.fixture
def fake_supabase():
    return FakeSupabase
