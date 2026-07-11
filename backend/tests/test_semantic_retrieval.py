from __future__ import annotations

from services import context_builder, goal_planning


class FakeResult:
    def __init__(self, data: list[dict]):
        self.data = data


class FakeRpc:
    def __init__(self, data: list[dict]):
        self.data = data

    def execute(self):
        return FakeResult(self.data)


class FakeSemanticDb:
    def __init__(self):
        self.rpc_calls: list[tuple[str, dict]] = []
        self.context_rows = [
            {
                "user_id": "user-a",
                "source_type": "copilot_message",
                "source_id": "msg-a",
                "title": "user_initiated",
                "content": "Discussed Freeside RAG retrieval.",
                "similarity": 0.94,
                "created_at": "2026-07-11T10:00:00",
            },
            {
                "user_id": "user-b",
                "source_type": "goal",
                "source_id": "goal-b",
                "title": "Private other-user goal",
                "content": "This must never leak.",
                "similarity": 0.99,
                "created_at": "2026-07-11T10:01:00",
            },
        ]

    def rpc(self, name: str, params: dict):
        self.rpc_calls.append((name, params))
        assert name == "match_copilot_context"
        user_id = params["p_user_id"]
        rows = [row for row in self.context_rows if row["user_id"] == user_id]
        rows.sort(key=lambda row: row["similarity"], reverse=True)
        return FakeRpc(rows[: params["p_match_count"]])


class FakeGoalDb:
    def __init__(self, similarity: float):
        self.similarity = similarity

    def rpc(self, name: str, params: dict):
        assert name == "match_user_goals"
        assert params["p_user_id"] == "user-a"
        return FakeRpc([
            {
                "goal_id": "goal-a",
                "title": "Ship Freeside semantic retrieval",
                "similarity": self.similarity,
            }
        ])


def test_relevant_history_scoped_to_requesting_user(monkeypatch):
    db = FakeSemanticDb()
    monkeypatch.setattr(context_builder, "embed_text", lambda text: [0.1, 0.2, 0.3])

    rows = context_builder.fetch_relevant_history(
        db,
        "user-a",
        "How should we add retrieval?",
        k=5,
    )

    assert db.rpc_calls[0][1]["p_user_id"] == "user-a"
    assert [row["source_id"] for row in rows] == ["msg-a"]
    assert all("other-user" not in row["content"] for row in rows)
    assert all(row["source_id"] != "goal-b" for row in rows)


def test_brain_dump_goal_similarity_suggests_link_vs_new(monkeypatch):
    monkeypatch.setattr(goal_planning, "embed_text", lambda text: [0.1, 0.2, 0.3])

    link = goal_planning.suggest_goal_link_for_brain_dump_item(
        FakeGoalDb(0.9),
        "user-a",
        "Add semantic retrieval to Co-Pilot",
        threshold=0.85,
    )
    create_new = goal_planning.suggest_goal_link_for_brain_dump_item(
        FakeGoalDb(0.7),
        "user-a",
        "Buy printer paper",
        threshold=0.85,
    )

    assert link == {
        "goal_id": "goal-a",
        "goal_title": "Ship Freeside semantic retrieval",
        "similarity": 0.9,
        "suggestion": "link_existing_goal",
    }
    assert create_new is None
