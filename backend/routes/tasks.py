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
from services.day_context import get_day_plan_focus

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
    # Fetch user profile for peak_focus_time and AI split context
    profile_resp = (
        supabase.table("profiles")
        .select("peak_focus_time, role, work_style")
        .eq("id", user_id)
        .single()
        .execute()
    )
    profile = profile_resp.data or {}
    peak_focus_time = profile.get("peak_focus_time")

    using_override = energy_score is not None
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
    pending = [t for t in all_tasks if t.get("status") == "pending"]
    active_parents = [
        t for t in all_tasks
        if t.get("status") == "active" and not t.get("parent_task_id")
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
    }


@router.post("/decompose-goal")
def decompose_goal_route(request: GoalDecomposeRequest):
    """
    Ask Gemini to break a goal into 5–8 structured tasks with cognitive load scores.
    Returns the task list for user review before inserting into the pool.
    """
    profile_resp = (
        supabase.table("profiles")
        .select("role, work_style")
        .eq("id", request.user_id)
        .single()
        .execute()
    )
    profile = profile_resp.data or {}

    tasks = decompose_goal(request.goal_title, request.category, request.timeframe, profile)
    return {"tasks": tasks, "goal_title": request.goal_title}


@router.post("/decompose-goal/confirm")
def confirm_decomposed_tasks(request: ConfirmTasksRequest):
    """Insert user-approved AI-decomposed tasks into the task pool."""
    inserted = []
    for t in request.tasks:
        row = supabase.table("tasks").insert({
            "user_id":              request.user_id,
            "title":                t["title"],
            "cognitive_load_score": t.get("cognitive_load_score", 5),
            "goal_id":              request.goal_id,
            "source":               "ai_decomposed",
        }).execute()
        if row.data:
            inserted.append(row.data[0])
    return {"inserted": len(inserted), "tasks": inserted}


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
def confirm_copilot_tasks(request: ConfirmBrainDumpRequest):
    """Insert user-approved Co-Pilot suggested tasks into the task pool."""
    inserted = []
    for t in request.tasks:
        row = supabase.table("tasks").insert({
            "user_id":              request.user_id,
            "title":                t["title"],
            "cognitive_load_score": t.get("cognitive_load_score", 5),
            "source":               "copilot_suggested",
        }).execute()
        if row.data:
            inserted.append(row.data[0])
    return {"inserted": len(inserted), "tasks": inserted}


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

    return {
        "xp_earned": xp_earned,
        "xp_total": new_xp,
        "task_id": task_id,
        "completed_at": now_iso,
        "parent_task_id": parent_id,
        "parent_progress_percent": parent_progress,
    }
