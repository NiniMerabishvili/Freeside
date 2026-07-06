"""Persist CLCS routing snapshots for thesis metrics and reroute audit."""
from __future__ import annotations

from datetime import datetime, timezone

from supabase import Client


def log_routing_snapshot(
    db: Client,
    user_id: str,
    routed_tasks: list[dict],
    energy_score: int,
    energy_level: str,
    effective_capacity: int,
) -> int:
    """Write one routing_logs row per pending task after CLCS routing."""
    if not routed_tasks:
        return 0

    now_iso = datetime.now(timezone.utc).isoformat()
    rows = []
    for task in routed_tasks:
        rows.append(
            {
                "user_id": user_id,
                "task_id": task.get("id"),
                "task_title": task.get("title"),
                "cognitive_load_score": task.get("cognitive_load_score"),
                "energy_score": energy_score,
                "energy_level": energy_level,
                "effective_capacity": effective_capacity,
                "delta": task.get("delta"),
                "was_rerouted": task.get("visible") is False,
                "unlock_score": task.get("unlock_score"),
                "routed_at": now_iso,
            }
        )

    try:
        db.table("routing_logs").insert(rows).execute()
        return len(rows)
    except Exception:
        # Fallback: log rerouted tasks only in session_logs
        rerouted = [row for row in rows if row["was_rerouted"]]
        for row in rerouted:
            try:
                db.table("session_logs").insert(
                    {
                        "user_id": user_id,
                        "task_id": row["task_id"],
                        "task_title": row["task_title"],
                        "cognitive_load_score": row["cognitive_load_score"],
                        "energy_score": energy_score,
                        "energy_level": energy_level,
                        "was_rerouted": True,
                        "started_at": now_iso,
                    }
                ).execute()
            except Exception:
                pass
        return len(rerouted)


def fetch_recent_copilot_summary(db: Client, user_id: str, limit: int = 8) -> str:
    """Summarise recent Co-Pilot interactions for day-planning context."""
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
        return "No recent Co-Pilot activity."

    if not rows:
        return "No recent Co-Pilot activity."

    parts = []
    for row in rows:
        msg_type = row.get("message_type") or "chat"
        ts = (row.get("created_at") or "")[:10]
        parts.append(f"- {msg_type} ({ts})")
    return "\n".join(parts)
