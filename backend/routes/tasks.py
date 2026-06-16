"""
Task routes — CRUD, routing by energy, and task completion with XP.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os
from supabase import create_client
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from services.router import route_tasks

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


@router.get("/routed")
def get_routed_tasks(user_id: str):
    """Get tasks routed by the cognitive load algorithm based on current energy."""
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
        # No energy set today — return all tasks unrouted
        tasks = (
            supabase.table("tasks")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "pending")
            .execute()
        )
        return {"energy_set": False, "tasks": tasks.data}

    energy = energy_log.data[0]
    energy_level = energy["confirmed_level"]
    energy_score = energy["confirmed_score"]

    # Get pending tasks
    tasks = (
        supabase.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "pending")
        .execute()
    )

    # Route tasks through the cognitive load algorithm
    routed = route_tasks(tasks.data, energy_level, energy_score)

    return {
        "energy_set": True,
        "energy_level": energy_level,
        "energy_score": energy_score,
        "tasks": routed,
    }


@router.post("/{task_id}/complete")
def complete_task(task_id: str, request: TaskCompleteRequest):
    """Mark a task complete, award XP, and log the session."""
    # Get the task
    task = (
        supabase.table("tasks")
        .select("*")
        .eq("id", task_id)
        .single()
        .execute()
        .data
    )

    # Update task status
    supabase.table("tasks").update(
        {"status": "completed", "completed_at": datetime.now().isoformat()}
    ).eq("id", task_id).execute()

    # Award XP
    xp_earned = task["cognitive_load_score"] * 10
    profile = (
        supabase.table("profiles")
        .select("xp_total")
        .eq("id", request.user_id)
        .single()
        .execute()
        .data
    )
    new_xp = (profile.get("xp_total") or 0) + xp_earned
    supabase.table("profiles").update({"xp_total": new_xp}).eq(
        "id", request.user_id
    ).execute()

    # Log the session
    supabase.table("session_logs").insert(
        {
            "user_id": request.user_id,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
        }
    ).execute()

    return {"xp_earned": xp_earned, "xp_total": new_xp, "task_id": task_id}
