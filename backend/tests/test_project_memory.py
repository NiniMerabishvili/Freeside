from __future__ import annotations

from services import project_memory


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, db: "FakeDb", name: str):
        self.db = db
        self.name = name
        self.filters: list[tuple[str, object]] = []
        self.payload: dict | None = None
        self.row_limit: int | None = None
        self.desc = False

    def select(self, *_args, **_kwargs):
        return self

    def insert(self, payload: dict):
        self.payload = {**payload, "id": f"{self.name}-{len(self.db.tables.get(self.name, [])) + 1}"}
        self.db.tables.setdefault(self.name, []).append(self.payload)
        return self

    def eq(self, field: str, value: object):
        self.filters.append((field, value))
        return self

    def order(self, _field: str, **kwargs):
        self.desc = bool(kwargs.get("desc"))
        return self

    def limit(self, count: int):
        self.row_limit = count
        return self

    def single(self):
        return self

    def execute(self):
        if self.payload is not None:
            return FakeResult([self.payload])
        rows = list(self.db.tables.get(self.name, []))
        for field, value in self.filters:
            rows = [row for row in rows if row.get(field) == value]
        if self.desc:
            rows = list(reversed(rows))
        if self.row_limit is not None:
            rows = rows[: self.row_limit]
        return FakeResult(rows[0] if rows and self.name == "profiles" else rows)


class FakeRpc:
    def __init__(self, rows):
        self.rows = rows

    def execute(self):
        return FakeResult(self.rows)


class FakeDb:
    def __init__(self):
        self.tables = {
            "profiles": [{"id": "user-1", "role": "freelance designer"}],
            "energy_logs": [{"user_id": "user-1", "confirmed_score": 6, "confirmed_level": "balanced"}],
            "project_memory_sources": [],
        }
        self.rpc_calls: list[tuple[str, dict]] = []

    def table(self, name: str):
        return FakeTable(self, name)

    def rpc(self, name: str, params: dict):
        self.rpc_calls.append((name, params))
        rows = [
            {
                "memory_id": row["id"],
                "title": row["title"],
                "source_type": row["source_type"],
                "content": row["content"],
                "chunk_index": row["chunk_index"],
                "similarity": 0.91,
                "created_at": row["created_at"],
            }
            for row in self.tables["project_memory_sources"]
            if row["user_id"] == params["p_user_id"]
        ]
        return FakeRpc(rows[: params["p_match_count"]])


def test_chunk_project_context_preserves_short_notes():
    chunks = project_memory.chunk_project_context("Brief intro.\n\nRequirements list.")

    assert chunks == ["Brief intro.\nRequirements list."]


def test_store_project_memory_embeds_and_inserts_chunks(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(project_memory, "embed_text", lambda text: [0.1] * 768)

    result = project_memory.store_project_memory(
        db,
        "user-1",
        title="Client launch",
        content="Build landing page.\n\nPrepare launch checklist.",
    )

    assert result["inserted"] == 1
    row = db.tables["project_memory_sources"][0]
    assert row["title"] == "Client launch"
    assert row["embedding"] == [0.1] * 768


def test_plan_from_project_memory_returns_grounded_milestones(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(project_memory, "embed_text", lambda text: [0.1] * 768)
    project_memory.store_project_memory(
        db,
        "user-1",
        title="Client launch",
        content="The next deliverable is a landing-page hero and pricing section.",
    )

    monkeypatch.setattr(
        project_memory.model_router,
        "generate_json",
        lambda *_args, **_kwargs: {
            "reply": "Use the launch context for one balanced work block.",
            "milestones": [
                {
                    "title": "Draft launch page structure",
                    "cognitive_load_score": 5,
                    "estimated_minutes": 60,
                    "source_refs": ["Client launch #0"],
                    "tasks": [
                        {
                            "title": "Outline hero and pricing sections",
                            "cognitive_load_score": 4,
                            "estimated_minutes": 30,
                            "source_refs": ["Client launch #0"],
                        }
                    ],
                }
            ],
            "blockers": [],
            "citations": ["Client launch #0"],
        },
    )

    plan = project_memory.plan_from_project_memory(
        db,
        "user-1",
        question="What should I work on next?",
        energy_score=6,
        energy_level="balanced",
    )

    assert plan["milestones"][0]["title"] == "Draft launch page structure"
    assert plan["citations"] == ["Client launch #0"]
    assert plan["retrieved_context"][0]["title"] == "Client launch"
