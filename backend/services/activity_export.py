"""User-facing activity summary export for profile CSV downloads."""
from __future__ import annotations

import csv
import io
from datetime import date

from postgrest.exceptions import APIError
from supabase import Client

from services.db_compat import is_missing_column_error
from services.xp import effective_task_xp, task_xp

ACTIVITY_COLUMNS = [
    "activity_type",
    "occurred_at",
    "title",
    "cognitive_load",
    "xp_earned",
    "energy_score",
    "energy_level",
    "was_rerouted",
]

SUMMARY_COLUMNS = ["metric", "value"]

SESSION_FIELDS_EXTENDED = (
    "task_id, task_title, cognitive_load_score, xp_earned, "
    "energy_score, energy_level, was_rerouted, completed_at"
)
SESSION_FIELDS_LEGACY = (
    "task_id, energy_score, energy_level, was_rerouted, completed_at"
)


def _session_xp(session: dict, task: dict | None = None) -> int:
    stored = session.get("xp_earned")
    if isinstance(stored, int):
        return stored
    if task:
        return effective_task_xp(task)
    load = session.get("cognitive_load_score")
    if isinstance(load, int):
        return task_xp(load)
    return 0


def _session_title(session: dict, task: dict | None = None) -> str:
    if session.get("task_title"):
        return str(session["task_title"])
    if task and task.get("title"):
        return str(task["title"])
    return "Completed task"


def _session_load(session: dict, task: dict | None = None) -> int | str:
    if isinstance(session.get("cognitive_load_score"), int):
        return session["cognitive_load_score"]
    if task and isinstance(task.get("cognitive_load_score"), int):
        return task["cognitive_load_score"]
    return ""


def _fetch_sessions(db: Client, user_id: str, start_iso: str, end_iso: str) -> list[dict]:
    try:
        resp = (
            db.table("session_logs")
            .select(SESSION_FIELDS_EXTENDED)
            .eq("user_id", user_id)
            .not_.is_("completed_at", "null")
            .gte("completed_at", start_iso)
            .lte("completed_at", end_iso)
            .order("completed_at", desc=False)
            .execute()
        )
        return resp.data or []
    except APIError as exc:
        if not is_missing_column_error(exc):
            raise

    resp = (
        db.table("session_logs")
        .select(SESSION_FIELDS_LEGACY)
        .eq("user_id", user_id)
        .not_.is_("completed_at", "null")
        .gte("completed_at", start_iso)
        .lte("completed_at", end_iso)
        .order("completed_at", desc=False)
        .execute()
    )
    return resp.data or []


def _fetch_completed_tasks(db: Client, user_id: str, start_iso: str, end_iso: str) -> list[dict]:
    try:
        resp = (
            db.table("tasks")
            .select("id, title, cognitive_load_score, xp_earned, completed_at, status")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .gte("completed_at", start_iso)
            .lte("completed_at", end_iso)
            .order("completed_at", desc=False)
            .execute()
        )
        return resp.data or []
    except APIError as exc:
        if not is_missing_column_error(exc):
            raise
        resp = (
            db.table("tasks")
            .select("id, title, cognitive_load_score, completed_at, status")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .gte("completed_at", start_iso)
            .lte("completed_at", end_iso)
            .order("completed_at", desc=False)
            .execute()
        )
        return resp.data or []


def export_user_activity(
    db: Client,
    user_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """Build a CSV activity log and summary stats from persisted session logs."""
    start_iso = start_date.isoformat()
    end_iso = f"{end_date.isoformat()}T23:59:59"

    sessions = _fetch_sessions(db, user_id, start_iso, end_iso)

    task_ids = [row["task_id"] for row in sessions if row.get("task_id")]
    task_map: dict[str, dict] = {}
    if task_ids:
        tasks_resp = (
            db.table("tasks")
            .select("id, title, cognitive_load_score, completed_at, status")
            .in_("id", task_ids)
            .execute()
        )
        task_map = {row["id"]: row for row in (tasks_resp.data or [])}

    if not sessions:
        completed_tasks = _fetch_completed_tasks(db, user_id, start_iso, end_iso)
        for task in completed_tasks:
            sessions.append(
                {
                    "task_id": task.get("id"),
                    "task_title": task.get("title"),
                    "cognitive_load_score": task.get("cognitive_load_score"),
                    "xp_earned": effective_task_xp(task),
                    "energy_score": "",
                    "energy_level": "",
                    "was_rerouted": "",
                    "completed_at": task.get("completed_at"),
                }
            )

    energy_resp = (
        db.table("energy_logs")
        .select("confirmed_score, confirmed_level, logged_at")
        .eq("user_id", user_id)
        .gte("logged_at", start_iso)
        .lte("logged_at", end_iso)
        .order("logged_at", desc=False)
        .execute()
    )
    energy_logs = energy_resp.data or []

    try:
        sleep_resp = (
            db.table("sleep_logs")
            .select("hours_slept, rested_score, logged_at")
            .eq("user_id", user_id)
            .gte("logged_at", start_iso)
            .lte("logged_at", end_iso)
            .order("logged_at", desc=False)
            .execute()
        )
        sleep_logs = sleep_resp.data or []
    except Exception:
        sleep_logs = []

    activity_rows: list[dict] = []
    total_xp = 0

    for session in sessions:
        task = task_map.get(session.get("task_id")) if session.get("task_id") else None
        xp = _session_xp(session, task)
        total_xp += xp
        activity_rows.append(
            {
                "activity_type": "task_completed",
                "occurred_at": session.get("completed_at") or "",
                "title": _session_title(session, task),
                "cognitive_load": _session_load(session, task),
                "xp_earned": xp,
                "energy_score": session.get("energy_score") or "",
                "energy_level": session.get("energy_level") or "",
                "was_rerouted": session.get("was_rerouted", ""),
            }
        )

    for log in energy_logs:
        activity_rows.append(
            {
                "activity_type": "energy_checkin",
                "occurred_at": log.get("logged_at") or "",
                "title": "Daily energy check-in",
                "cognitive_load": "",
                "xp_earned": "",
                "energy_score": log.get("confirmed_score") or "",
                "energy_level": log.get("confirmed_level") or "",
                "was_rerouted": "",
            }
        )

    for log in sleep_logs:
        hours = log.get("hours_slept")
        rested = log.get("rested_score")
        activity_rows.append(
            {
                "activity_type": "sleep_checkin",
                "occurred_at": log.get("logged_at") or "",
                "title": f"Sleep log · {hours}h · rested {rested}/5",
                "cognitive_load": "",
                "xp_earned": "",
                "energy_score": rested or "",
                "energy_level": f"{hours}h" if hours is not None else "",
                "was_rerouted": "",
            }
        )

    activity_rows.sort(key=lambda row: str(row.get("occurred_at") or ""))

    task_completions = sum(1 for row in activity_rows if row["activity_type"] == "task_completed")
    energy_scores = [
        log["confirmed_score"]
        for log in energy_logs
        if isinstance(log.get("confirmed_score"), int)
    ]
    avg_energy = round(sum(energy_scores) / len(energy_scores), 2) if energy_scores else 0.0

    rested_scores = [
        float(log["rested_score"])
        for log in sleep_logs
        if log.get("rested_score") is not None
    ]
    avg_rested = round(sum(rested_scores) / len(rested_scores), 2) if rested_scores else 0.0

    summary_rows = [
        {"metric": "period_start", "value": start_date.isoformat()},
        {"metric": "period_end", "value": end_date.isoformat()},
        {"metric": "tasks_completed", "value": task_completions},
        {"metric": "total_xp_earned", "value": total_xp},
        {"metric": "energy_checkins", "value": len(energy_logs)},
        {"metric": "sleep_checkins", "value": len(sleep_logs)},
        {"metric": "average_energy_score", "value": avg_energy},
        {"metric": "average_rested_score", "value": avg_rested},
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=SUMMARY_COLUMNS)
    writer.writeheader()
    writer.writerows(summary_rows)
    buffer.write("\n")
    detail_writer = csv.DictWriter(buffer, fieldnames=ACTIVITY_COLUMNS)
    detail_writer.writeheader()
    detail_writer.writerows(activity_rows)

    return {
        "csv_string": buffer.getvalue(),
        "summary": {
            "tasks_completed": task_completions,
            "total_xp_earned": total_xp,
            "energy_checkins": len(energy_logs),
            "sleep_checkins": len(sleep_logs),
            "average_energy_score": avg_energy,
            "average_rested_score": avg_rested,
        },
        "activity_count": len(activity_rows),
        "window": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
    }
