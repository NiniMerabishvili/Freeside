from __future__ import annotations

from services.xp import effective_task_xp, sync_profile_xp, task_xp


def test_task_xp_scales_with_cognitive_load():
    assert task_xp(1) == 10
    assert task_xp(7) == 70
    assert task_xp(0) == 10


def test_effective_task_xp_prefers_stored_completion_xp():
    assert effective_task_xp({"xp_earned": 85, "cognitive_load_score": 4}) == 85
    assert effective_task_xp({"cognitive_load_score": 4}) == 40
    assert effective_task_xp({"title": "No score"}) == 0


def test_sync_profile_xp_uses_completed_tasks_only(fake_supabase):
    db = fake_supabase({
        "tasks": [
            {"user_id": "u1", "status": "completed", "cognitive_load_score": 3},
            {"user_id": "u1", "status": "completed", "cognitive_load_score": 6},
            {"user_id": "u1", "status": "pending", "cognitive_load_score": 10},
            {"user_id": "u2", "status": "completed", "cognitive_load_score": 10},
        ],
        "profiles": [{"id": "u1", "xp_total": 0}],
    })

    total = sync_profile_xp(db, "u1")

    assert total == 90
    assert db.tables["profiles"][0]["xp_total"] == 90
