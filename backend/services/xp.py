"""XP helpers — reward scales with task cognitive load (1–10)."""
from __future__ import annotations

from supabase import Client


def task_xp(cognitive_load_score: int) -> int:
    """XP earned when completing a task at the given difficulty."""
    return max(1, cognitive_load_score) * 10


def effective_task_xp(task: dict) -> int:
    stored = task.get("xp_earned")
    if isinstance(stored, int):
        return stored
    load = task.get("cognitive_load_score")
    if isinstance(load, int):
        return task_xp(load)
    return 0


def sync_profile_xp(db: Client, user_id: str) -> int:
    """Recompute profile XP from completed tasks (uses cognitive_load_score only)."""
    resp = (
        db.table("tasks")
        .select("cognitive_load_score")
        .eq("user_id", user_id)
        .eq("status", "completed")
        .execute()
    )
    total = sum(effective_task_xp(task) for task in (resp.data or []))
    db.table("profiles").update({"xp_total": total}).eq("id", user_id).execute()
    return total
