"""Persist and retrieve Co-Pilot conversation for day planning."""
from __future__ import annotations

from supabase import Client


def fetch_recent_copilot_conversation(db: Client, user_id: str, limit: int = 12) -> str:
    """
    Return recent Co-Pilot chat as readable transcript for AI day planning.
    Falls back to message-type summary if content columns are missing.
    """
    try:
        resp = (
            db.table("copilot_logs")
            .select("message_type, user_message, assistant_reply, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = list(reversed(resp.data or []))
    except Exception:
        return _fallback_summary(db, user_id, limit)

    parts: list[str] = []
    for row in rows:
        user_msg = (row.get("user_message") or "").strip()
        assistant = (row.get("assistant_reply") or "").strip()
        ts = (row.get("created_at") or "")[:10]
        if user_msg:
            parts.append(f"[{ts}] User: {user_msg[:800]}")
        if assistant:
            parts.append(f"[{ts}] Co-Pilot: {assistant[:800]}")
        if not user_msg and not assistant:
            msg_type = row.get("message_type") or "chat"
            parts.append(f"[{ts}] ({msg_type})")

    if parts:
        return "\n".join(parts)
    return _fallback_summary(db, user_id, limit)


def fetch_recent_copilot_turns(db: Client, user_id: str, limit: int = 6) -> list[dict]:
    """
    Return recent Co-Pilot exchanges as structured [{role, content}] turns for
    the new context-injection chat (oldest first).
    """
    try:
        resp = (
            db.table("copilot_logs")
            .select("user_message, assistant_reply, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = list(reversed(resp.data or []))
    except Exception:
        return []

    turns: list[dict] = []
    for row in rows:
        user_msg = (row.get("user_message") or "").strip()
        assistant = (row.get("assistant_reply") or "").strip()
        if user_msg:
            turns.append({"role": "user", "content": user_msg[:2000]})
        if assistant:
            turns.append({"role": "assistant", "content": assistant[:2000]})
    return turns


def _fallback_summary(db: Client, user_id: str, limit: int) -> str:
    try:
        resp = (
            db.table("copilot_logs")
            .select("message_type, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = resp.data or []
    except Exception:
        return "No recent Co-Pilot conversation."

    if not rows:
        return "No recent Co-Pilot conversation."

    return "\n".join(
        f"- {r.get('message_type') or 'chat'} ({(r.get('created_at') or '')[:10]})"
        for r in rows
    )


def log_copilot_exchange(
    db: Client,
    *,
    user_id: str,
    message_type: str,
    user_message: str,
    assistant_reply: str,
    task_id: str | None = None,
    energy_level: str | None = None,
) -> None:
    payload = {
        "user_id": user_id,
        "message_type": message_type,
        "task_id": task_id,
        "user_message": user_message[:4000] if user_message else None,
        "assistant_reply": assistant_reply[:4000] if assistant_reply else None,
        "energy_level_at_time": energy_level,
    }
    try:
        db.table("copilot_logs").insert(payload).execute()
    except Exception:
        # Older schema without message columns
        db.table("copilot_logs").insert({
            "user_id": user_id,
            "message_type": message_type,
            "task_id": task_id,
            "energy_level_at_time": energy_level,
        }).execute()
