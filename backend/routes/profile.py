"""Profile routes — activity summary and CSV export."""
import io
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from postgrest.exceptions import APIError
from supabase import create_client

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from services.activity_export import export_user_activity
from services.db_compat import is_missing_column_error
from services.xp import effective_task_xp, sync_profile_xp

router = APIRouter()

supabase = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)


def _fetch_recent_sessions(user_id: str) -> list[dict]:
    extended_select = (
        "id, task_id, task_title, cognitive_load_score, xp_earned, "
        "completed_at, energy_score, energy_level"
    )
    legacy_select = "id, task_id, completed_at, energy_score, energy_level, was_rerouted"

    try:
        resp = (
            supabase.table("session_logs")
            .select(extended_select)
            .eq("user_id", user_id)
            .not_.is_("completed_at", "null")
            .order("completed_at", desc=True)
            .limit(20)
            .execute()
        )
        return resp.data or []
    except APIError as exc:
        if not is_missing_column_error(exc):
            raise

    resp = (
        supabase.table("session_logs")
        .select(legacy_select)
        .eq("user_id", user_id)
        .not_.is_("completed_at", "null")
        .order("completed_at", desc=True)
        .limit(20)
        .execute()
    )
    sessions = resp.data or []
    task_ids = [row["task_id"] for row in sessions if row.get("task_id")]
    task_map: dict = {}
    if task_ids:
        tasks_resp = (
            supabase.table("tasks")
            .select("id, title, cognitive_load_score")
            .in_("id", task_ids)
            .execute()
        )
        task_map = {row["id"]: row for row in (tasks_resp.data or [])}

    enriched = []
    for row in sessions:
        task = task_map.get(row.get("task_id"))
        enriched.append(
            {
                **row,
                "task_title": (task or {}).get("title"),
                "cognitive_load_score": (task or {}).get("cognitive_load_score"),
                "xp_earned": effective_task_xp(task or {}),
            }
        )
    return enriched


def _fetch_recent_completed_tasks(user_id: str) -> list[dict]:
    try:
        resp = (
            supabase.table("tasks")
            .select("id, title, cognitive_load_score, xp_earned, completed_at")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .order("completed_at", desc=True)
            .limit(20)
            .execute()
        )
    except APIError as exc:
        if not is_missing_column_error(exc):
            raise
        resp = (
            supabase.table("tasks")
            .select("id, title, cognitive_load_score, completed_at")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .order("completed_at", desc=True)
            .limit(20)
            .execute()
        )

    return [
        {
            "id": task.get("id"),
            "task_id": task.get("id"),
            "task_title": task.get("title"),
            "cognitive_load_score": task.get("cognitive_load_score"),
            "xp_earned": effective_task_xp(task),
            "completed_at": task.get("completed_at"),
            "energy_score": None,
            "energy_level": None,
        }
        for task in (resp.data or [])
    ]


@router.get("/stats")
def profile_stats(user_id: str = Query(...)):
    """Sync profile XP from completed tasks and return recent completion activity."""
    xp_total = sync_profile_xp(supabase, user_id)

    sessions = _fetch_recent_sessions(user_id)
    if not sessions:
        sessions = _fetch_recent_completed_tasks(user_id)

    return {
        "user_id": user_id,
        "xp_total": xp_total,
        "recent_completions": sessions,
    }


@router.get("/activity/summary")
def activity_summary(
    user_id: str = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    """Return activity summary stats for the profile export preview."""
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date.")

    sync_profile_xp(supabase, user_id)
    result = export_user_activity(supabase, user_id, start_date, end_date)
    return {
        "user_id": user_id,
        "window": result["window"],
        "summary": result["summary"],
        "activity_count": result["activity_count"],
    }


@router.get("/activity/export")
def export_activity_csv(
    user_id: str = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    """Download a CSV activity log for the selected time window."""
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date.")

    sync_profile_xp(supabase, user_id)
    result = export_user_activity(supabase, user_id, start_date, end_date)
    filename = f"freeside_activity_{user_id[:8]}_{start_date}_{end_date}.csv"

    return StreamingResponse(
        io.StringIO(result["csv_string"]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
