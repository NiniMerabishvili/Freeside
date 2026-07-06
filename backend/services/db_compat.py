"""Helpers for optional Supabase columns not yet migrated."""
from __future__ import annotations


def is_missing_column_error(exc: Exception) -> bool:
    text = str(exc).lower()
    if isinstance(getattr(exc, "args", None), tuple) and exc.args:
        first = exc.args[0]
        if isinstance(first, dict):
            text = f"{first.get('message', '')} {first.get('code', '')}".lower()
    return (
        "xp_earned" in text
        or "step_order" in text
        or "task_title" in text
        or "avatar_url" in text
        or "could not find" in text
        or "pgrst204" in text
        or "42703" in text
    )


def update_task_completed(db, task_id: str, user_id: str, now_iso: str, xp_earned: int):
    """Mark task complete. XP is synced via cognitive_load_score — no xp_earned column required."""
    del xp_earned  # kept for caller API; stored in session_logs when column exists
    return (
        db.table("tasks")
        .update({"status": "completed", "completed_at": now_iso})
        .eq("id", task_id)
        .eq("user_id", user_id)
        .execute()
    )
