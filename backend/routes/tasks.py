"""
Task routes — CRUD, routing by energy, and task completion with XP.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import os
from supabase import create_client
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from services.ai import decompose_goal, parse_brain_dump, break_down_task
from services.xp import task_xp, sync_profile_xp
from services.db_compat import update_task_completed
from services.routing_log import log_routing_snapshot
from services.task_split import route_with_splits, maybe_complete_parent, parent_progress_percent
from services.day_context import get_day_plan_focus, sync_user_clickup_tasks, probe_calendar_health
from services.goal_planning import (
    assign_milestones_to_days,
    forecast_energy_landscape,
    insert_scheduled_milestones,
    sync_goal_progress,
    sync_milestone_progress,
    insert_copilot_milestones,
    task_is_due_for_today,
)
from services.daily_scheduler import (
    build_milestone_groups,
    generate_daily_schedule,
    milestone_task_is_routable_today,
)

router = APIRouter()

supabase = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)


class TaskCreateRequest(BaseModel):
    user_id: str
    title: str
    description: Optional[str] = None
    cognitive_load_score: int
    goal_id: Optional[str] = None


class TaskCompleteRequest(BaseModel):
    user_id: str
    was_rerouted: bool = False      # True if CLCS marked this task as deferred
    energy_score: int | None = None # user's confirmed energy at time of completion
    energy_level: str | None = None


class GoalDecomposeRequest(BaseModel):
    user_id: str
    goal_id: Optional[str] = None
    goal_title: str
    category: str
    timeframe: str


class BrainDumpRequest(BaseModel):
    user_id: str
    raw_text: str


class ConfirmTasksRequest(BaseModel):
    user_id: str
    goal_id: Optional[str] = None
    tasks: list


class ConfirmBrainDumpRequest(BaseModel):
    user_id: str
    tasks: list


class ConfirmCopilotMilestonesRequest(BaseModel):
    user_id: str
    milestones: list


class TaskBreakdownRequest(BaseModel):
    user_id: str
    task_id: Optional[str] = None
    task_title: str


class TaskUpdateRequest(BaseModel):
    user_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    cognitive_load_score: Optional[int] = None


@router.get("/completed")
def get_completed_tasks(user_id: str, limit: int = 30):
    """Return recently completed tasks for the Tasks Done section."""
    result = (
        supabase.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "completed")
        .order("completed_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


@router.post("/breakdown")
def breakdown_task(request: TaskBreakdownRequest):
    """
    Generate energy-aware micro-steps for a single task.
    Used by the task card Break down button — returns structured steps, not chat prose.
    """
    profile_resp = (
        supabase.table("profiles")
        .select("role, work_style")
        .eq("id", request.user_id)
        .single()
        .execute()
    )
    profile = profile_resp.data or {}

    energy_log = (
        supabase.table("energy_logs")
        .select("confirmed_level, confirmed_score")
        .eq("user_id", request.user_id)
        .order("logged_at", desc=True)
        .limit(1)
        .execute()
    )
    energy = energy_log.data[0] if energy_log.data else {}
    energy_level = energy.get("confirmed_level") or "balanced"
    energy_score = energy.get("confirmed_score") or 5

    steps = break_down_task(
        request.task_title,
        energy_level,
        energy_score,
        profile,
    )

    # Log for PFI breakdown metric
    try:
        supabase.table("copilot_logs").insert({
            "user_id":      request.user_id,
            "message_type": "break_down",
            "task_id":      request.task_id,
        }).execute()
    except Exception:
        pass

    return {
        "steps": steps,
        "energy_level": energy_level,
        "energy_score": energy_score,
    }


@router.post("/")
def create_task(request: TaskCreateRequest):
    """Create a new task with a cognitive load score."""
    result = (
        supabase.table("tasks")
        .insert(
            {
                "user_id": request.user_id,
                "title": request.title,
                "description": request.description,
                "cognitive_load_score": request.cognitive_load_score,
                "goal_id": request.goal_id,
            }
        )
        .execute()
    )
    return result.data[0] if result.data else {"error": "Failed to create task"}


@router.get("/")
def get_tasks(user_id: str):
    """Get all tasks for a user."""
    result = (
        supabase.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def _score_to_level(score: int) -> str:
    if score >= 7:
        return "high"
    if score >= 4:
        return "balanced"
    return "low"


@router.get("/routed")
def get_routed_tasks(
    user_id: str,
    log_routing: bool = False,
    energy_score: Optional[int] = None,
    energy_level: Optional[str] = None,
):
    """
    Get tasks routed by the CLCS algorithm based on today's energy.
    Returns CLCS metadata (effective_capacity, peak_boost, counts) alongside tasks.
    When log_routing=true, persists a routing snapshot (including rerouted tasks).

    Optional energy_score / energy_level override live slider previews before confirm.
    """
    # Fetch user profile for routing, calendar, and daily scheduling
    profile_resp = (
        supabase.table("profiles")
        .select(
            "peak_focus_time, role, work_style, daily_work_hours, "
            "google_calendar_connected, google_refresh_token"
        )
        .eq("id", user_id)
        .single()
        .execute()
    )
    profile = profile_resp.data or {}
    peak_focus_time = profile.get("peak_focus_time")

    using_override = energy_score is not None

    sync_warnings: list[dict] = []

    # Import live ClickUp tasks + surface integration health (Phase 0).
    if not using_override:
        try:
            _, cu_warnings = sync_user_clickup_tasks(supabase, user_id)
            sync_warnings.extend(w.to_dict() for w in cu_warnings)
        except Exception:
            pass
        if profile.get("google_calendar_connected") and profile.get("google_refresh_token"):
            cal_warn = probe_calendar_health(profile.get("google_refresh_token"))
            if cal_warn:
                sync_warnings.append(cal_warn.to_dict())
    if using_override:
        energy_score = max(1, min(10, energy_score))
        energy_level = energy_level or _score_to_level(energy_score)
    else:
        # Get today's latest energy log
        energy_log = (
            supabase.table("energy_logs")
            .select("*")
            .eq("user_id", user_id)
            .order("logged_at", desc=True)
            .limit(1)
            .execute()
        )

        if not energy_log.data:
            tasks = (
                supabase.table("tasks")
                .select("*")
                .eq("user_id", user_id)
                .eq("status", "pending")
                .execute()
            )
            return {
                "energy_set": False,
                "tasks": tasks.data,
                "active_count": 0,
                "rerouted_count": 0,
                "sync_warnings": sync_warnings,
            }

        energy       = energy_log.data[0]
        energy_level = energy["confirmed_level"]
        energy_score = energy["confirmed_score"]

    tasks = (
        supabase.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .in_("status", ["pending", "active"])
        .execute()
    )
    all_tasks = tasks.data or []
    pending = [
        t for t in all_tasks
        if t.get("status") == "pending"
        and task_is_due_for_today(t)
        and not t.get("is_milestone")
    ]

    daily_schedule = None
    if not using_override:
        daily_schedule = generate_daily_schedule(
            supabase, user_id, profile, energy_score, peak_focus_time
        )

    pending = [
        t for t in pending
        if (milestone_task_is_routable_today(t) if t.get("milestone_id") else True)
    ]

    # Attach milestone titles for UI grouping
    milestone_ids = {t["milestone_id"] for t in pending if t.get("milestone_id")}
    milestone_titles: dict[str, str] = {}
    if milestone_ids:
        try:
            ms_rows = (
                supabase.table("milestones")
                .select("id, title")
                .in_("id", list(milestone_ids))
                .execute()
            ).data or []
            milestone_titles = {m["id"]: m["title"] for m in ms_rows}
        except Exception:
            pass
    for t in pending:
        mid = t.get("milestone_id")
        if mid and mid in milestone_titles:
            t["milestone_title"] = milestone_titles[mid]

    active_parents = [
        t for t in all_tasks
        if t.get("status") == "active"
        and not t.get("parent_task_id")
        and not t.get("is_milestone")
        and not t.get("milestone_id")
    ]

    result = route_with_splits(
        supabase,
        user_id,
        pending,
        active_parents,
        energy_score,
        peak_focus_time,
        profile,
        focus_titles=get_day_plan_focus(user_id),
    )

    if log_routing and not using_override:
        log_routing_snapshot(
            supabase,
            user_id,
            result["tasks"],
            energy_score,
            energy_level,
            result["effective_capacity"],
        )

    milestone_groups = build_milestone_groups(
        supabase,
        result["tasks"],
        (daily_schedule or {}).get("deferred_tasks"),
    )

    return {
        "energy_set":          True,
        "energy_level":        energy_level,
        "energy_score":        energy_score,
        "effective_capacity":  result["effective_capacity"],
        "peak_boost":          result["peak_boost"],
        "tasks":               result["tasks"],
        "active_count":        result["active_count"],
        "rerouted_count":      result["rerouted_count"],
        "parent_groups":       result.get("parent_groups", []),
        "milestone_groups":    milestone_groups,
        "daily_schedule":      daily_schedule,
        "sync_warnings":       sync_warnings,
    }


@router.post("/decompose-goal")
def decompose_goal_route(request: GoalDecomposeRequest):
    """
    Break a goal into 4–6 substantive milestones with multi-day schedule preview.
    Returns milestones for user review before inserting.
    """
    profile_resp = (
        supabase.table("profiles")
        .select("role, work_style, google_calendar_connected, google_refresh_token")
        .eq("id", request.user_id)
        .single()
        .execute()
    )
    profile = profile_resp.data or {}

    milestones, ai_fallback = decompose_goal(
        request.goal_title, request.category, request.timeframe, profile
    )
    landscape = forecast_energy_landscape(supabase, request.user_id, profile)
    scheduled = assign_milestones_to_days(milestones, landscape)
    return {
        "tasks": scheduled,
        "milestones": scheduled,
        "goal_title": request.goal_title,
        "landscape": landscape,
        "ai_fallback": ai_fallback,
    }


@router.post("/decompose-goal/confirm")
def confirm_decomposed_tasks(request: ConfirmTasksRequest):
    """Insert approved milestones with multi-day scheduling (not all into today)."""
    if not request.goal_id:
        raise HTTPException(status_code=400, detail="goal_id is required for milestone planning")

    profile_resp = (
        supabase.table("profiles")
        .select("role, work_style, google_calendar_connected, google_refresh_token")
        .eq("id", request.user_id)
        .single()
        .execute()
    )
    profile = profile_resp.data or {}

    return insert_scheduled_milestones(
        supabase,
        request.user_id,
        request.goal_id,
        request.tasks,
        profile,
    )


@router.post("/brain-dump")
def brain_dump_route(request: BrainDumpRequest):
    """
    Parse a free-text brain dump into structured tasks via Gemini.
    Returns the parsed list for user review before inserting.
    """
    profile_resp = (
        supabase.table("profiles")
        .select("role")
        .eq("id", request.user_id)
        .single()
        .execute()
    )
    profile = profile_resp.data or {}

    tasks = parse_brain_dump(request.raw_text, profile)
    return {"tasks": tasks}


@router.post("/copilot-suggestions/confirm")
def confirm_copilot_tasks(request: ConfirmCopilotMilestonesRequest):
    """Insert Co-Pilot suggested milestones + child tasks."""
    profile_resp = (
        supabase.table("profiles")
        .select("role, work_style, peak_focus_time, daily_work_hours")
        .eq("id", request.user_id)
        .single()
        .execute()
    )
    profile = profile_resp.data or {}
    return insert_copilot_milestones(
        supabase,
        request.user_id,
        request.milestones,
        profile,
    )


@router.post("/brain-dump/confirm")
def confirm_brain_dump_tasks(request: ConfirmBrainDumpRequest):
    """Insert user-approved brain-dump tasks into the task pool."""
    inserted = []
    for t in request.tasks:
        row = supabase.table("tasks").insert({
            "user_id":              request.user_id,
            "title":                t["title"],
            "cognitive_load_score": t.get("cognitive_load_score", 5),
            "source":               "brain_dump",
        }).execute()
        if row.data:
            inserted.append(row.data[0])
    return {"inserted": len(inserted), "tasks": inserted}


@router.patch("/{task_id}")
def update_task(task_id: str, request: TaskUpdateRequest):
    """Update a pending task's title, description, or cognitive load."""
    updates: dict = {}
    if request.title is not None:
        updates["title"] = request.title.strip()
    if request.description is not None:
        updates["description"] = request.description.strip() or None
    if request.cognitive_load_score is not None:
        updates["cognitive_load_score"] = max(1, min(10, request.cognitive_load_score))

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = (
        supabase.table("tasks")
        .update(updates)
        .eq("id", task_id)
        .eq("user_id", request.user_id)
        .eq("status", "pending")
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Task not found")
    return result.data[0]


@router.delete("/{task_id}")
def delete_task(task_id: str, user_id: str):
    """Delete a task owned by the user."""
    result = (
        supabase.table("tasks")
        .delete()
        .eq("id", task_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Task not found")

    sync_profile_xp(supabase, user_id)
    return {"status": "deleted", "task_id": task_id}


def _insert_session_log(payload: dict) -> None:
    """Insert session log, falling back if optional activity columns are missing."""
    legacy_keys = (
        "user_id",
        "task_id",
        "started_at",
        "completed_at",
        "was_rerouted",
        "energy_score",
        "energy_level",
    )

    try:
        supabase.table("session_logs").insert(payload).execute()
        return
    except Exception:
        legacy_payload = {key: payload[key] for key in legacy_keys if key in payload}
        supabase.table("session_logs").insert(legacy_payload).execute()


@router.post("/{task_id}/complete")
def complete_task(task_id: str, request: TaskCompleteRequest):
    """Mark a task complete, award XP, and log the session."""
    task_resp = (
        supabase.table("tasks")
        .select("*")
        .eq("id", task_id)
        .eq("user_id", request.user_id)
        .execute()
    )
    task_rows = task_resp.data or []
    if not task_rows:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_rows[0]

    if task.get("status") == "completed":
        xp_total = sync_profile_xp(supabase, request.user_id)
        return {
            "xp_earned": 0,
            "xp_total": xp_total,
            "task_id": task_id,
            "already_completed": True,
            "completed_at": task.get("completed_at"),
        }

    load_score = task.get("cognitive_load_score")
    if not isinstance(load_score, int):
        raise HTTPException(status_code=400, detail="Task is missing a valid cognitive load score.")

    xp_earned = task_xp(load_score)
    now_iso = datetime.now(timezone.utc).isoformat()

    update_resp = update_task_completed(
        supabase, task_id, request.user_id, now_iso, xp_earned
    )

    if not update_resp.data:
        raise HTTPException(status_code=500, detail="Failed to mark task complete.")

    _insert_session_log(
        {
            "user_id": request.user_id,
            "task_id": task_id,
            "task_title": task.get("title"),
            "cognitive_load_score": load_score,
            "xp_earned": xp_earned,
            "started_at": now_iso,
            "completed_at": now_iso,
            "was_rerouted": request.was_rerouted,
            "energy_score": request.energy_score,
            "energy_level": request.energy_level,
        }
    )

    new_xp = sync_profile_xp(supabase, request.user_id)

    parent_id = task.get("parent_task_id")
    parent_progress = None
    if parent_id:
        maybe_complete_parent(supabase, request.user_id, parent_id)
        parent_progress = parent_progress_percent(supabase, parent_id)

    goal_progress = None
    goal_id = task.get("goal_id")
    milestone_id = task.get("milestone_id")
    milestone_progress = None

    if milestone_id:
        milestone_progress = sync_milestone_progress(supabase, milestone_id)
        ms_resp = (
            supabase.table("milestones")
            .select("goal_id")
            .eq("id", milestone_id)
            .single()
            .execute()
        )
        if ms_resp.data and ms_resp.data.get("goal_id"):
            goal_id = ms_resp.data["goal_id"]

    if goal_id and (
        task.get("is_milestone")
        or task.get("source") == "goal_milestone"
        or milestone_id
    ):
        goal_progress = sync_goal_progress(supabase, goal_id)

    return {
        "xp_earned": xp_earned,
        "xp_total": new_xp,
        "task_id": task_id,
        "completed_at": now_iso,
        "parent_task_id": parent_id,
        "parent_progress_percent": parent_progress,
        "goal_id": goal_id,
        "goal_progress_percent": goal_progress,
        "milestone_id": milestone_id,
        "milestone_progress_percent": milestone_progress,
    }
