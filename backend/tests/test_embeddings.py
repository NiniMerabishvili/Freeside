from __future__ import annotations

from services import embeddings


class FakeResult:
    def __init__(self, data: list[dict] | None = None):
        self.data = data or []


class FakeTable:
    def __init__(self, db: "FakeSupabase", name: str):
        self.db = db
        self.name = name
        self.filters: list[tuple[str, object]] = []
        self.payload: dict | None = None
        self.on_conflict: str | None = None

    def update(self, payload: dict):
        self.payload = payload
        self.db.calls.append(("update", self.name, payload, self.filters))
        return self

    def upsert(self, payload: dict, **kwargs):
        self.payload = payload
        self.on_conflict = kwargs.get("on_conflict")
        self.db.calls.append(("upsert", self.name, payload, self.on_conflict))
        return self

    def eq(self, field: str, value: object):
        self.filters.append((field, value))
        return self

    def execute(self):
        return FakeResult([self.payload] if self.payload else [])


class FakeSupabase:
    def __init__(self):
        self.calls: list[tuple] = []

    def table(self, name: str):
        return FakeTable(self, name)


def _embedding() -> list[float]:
    return [0.1] * embeddings.EMBEDDING_DIMENSIONS


def test_task_completion_embedding_updates_task(monkeypatch):
    db = FakeSupabase()
    monkeypatch.setattr(embeddings, "embed_text", lambda text: _embedding())
    monkeypatch.setattr(
        embeddings,
        "enqueue_embedding_write",
        lambda fn, *args, **kwargs: fn(*args, **kwargs),
    )

    embeddings.enqueue_task_completion_embedding(
        db,
        {
            "id": "task-1",
            "user_id": "user-1",
            "title": "Finish chapter",
            "description": "Write the RAG migration section",
            "status": "completed",
        },
    )

    assert db.calls[0][0] == "update"
    assert db.calls[0][1] == "tasks"
    assert db.calls[0][2]["embedding"] == _embedding()


def test_goal_creation_embedding_updates_goal(monkeypatch):
    db = FakeSupabase()
    monkeypatch.setattr(embeddings, "embed_text", lambda text: _embedding())
    monkeypatch.setattr(
        embeddings,
        "enqueue_embedding_write",
        lambda fn, *args, **kwargs: fn(*args, **kwargs),
    )

    embeddings.enqueue_goal_creation_embedding(
        db,
        {
            "id": "goal-1",
            "user_id": "user-1",
            "title": "Ship Freeside RAG",
            "category": "thesis",
            "timeframe": "3_months",
        },
    )

    assert db.calls[0][0] == "update"
    assert db.calls[0][1] == "goals"
    assert db.calls[0][2]["embedding"] == _embedding()


def test_copilot_turn_embedding_upserts_message(monkeypatch):
    db = FakeSupabase()
    monkeypatch.setattr(embeddings, "embed_text", lambda text: _embedding())
    monkeypatch.setattr(
        embeddings,
        "enqueue_embedding_write",
        lambda fn, *args, **kwargs: fn(*args, **kwargs),
    )

    embeddings.enqueue_copilot_turn_embedding(
        db,
        {
            "id": "turn-1",
            "user_id": "user-1",
            "message_type": "user_initiated",
            "user_message": "Plan the RAG infra",
            "assistant_reply": "Let's add pgvector first.",
        },
    )

    assert db.calls[0][0] == "upsert"
    assert db.calls[0][1] == "copilot_message_embeddings"
    assert db.calls[0][2]["message_id"] == "turn-1"
    assert db.calls[0][2]["embedding"] == _embedding()
    assert db.calls[0][3] == "message_id"
