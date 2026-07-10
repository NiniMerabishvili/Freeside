"""Goal routes — list goals with milestones, forecast, and create."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from services.goal_planning import (
    assign_milestones_to_days,
    fetch_goals_with_milestones,
    forecast_energy_landscape,
    insert_scheduled_milestones,
)
from services.ai import decompose_goal

router = APIRouter()

supabase = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)


class GoalCreateRequest(BaseModel):
    user_id: str
    title: str
    category: str = "work"
    timeframe: str = "3_months"


class MilestonePreviewRequest(BaseModel):
    user_id: str
    milestones: list


class GoalPlanRequest(BaseModel):
    user_id: str
    milestones: list


def _load_profile(user_id: str) -> dict:
    resp = (
        supabase.table("profiles")
        .select(
            "role, work_style, peak_focus_time, google_calendar_connected, google_refresh_token"
        )
        .eq("id", user_id)
        .single()
        .execute()
    )
    return resp.data or {}


@router.get("/")
def list_goals(user_id: str):
    """Active goals with milestone progress and schedule."""
    return {"goals": fetch_goals_with_milestones(supabase, user_id)}


@router.get("/forecast")
def get_capacity_forecast(user_id: str, days: int = 14):
    """14-day predicted energy/calendar capacity landscape."""
    profile = _load_profile(user_id)
    landscape = forecast_energy_landscape(supabase, user_id, profile, horizon_days=min(days, 21))
    return {"landscape": landscape}


@router.post("/")
def create_goal(request: GoalCreateRequest):
    """Create a new active goal (milestones planned separately)."""
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Goal title is required")

    existing = (
        supabase.table("goals")
        .select("id")
        .eq("user_id", request.user_id)
        .eq("is_active", True)
        .execute()
    )
    if len(existing.data or []) >= 3:
        raise HTTPException(status_code=400, detail="Maximum 3 active goals")

    try:
        row = supabase.table("goals").insert({
            "user_id": request.user_id,
            "title": title[:200],
            "category": request.category,
            "timeframe": request.timeframe,
            "is_active": True,
            "progress_percent": 0,
        }).execute()
    except Exception:
        row = supabase.table("goals").insert({
            "user_id": request.user_id,
            "title": title[:200],
            "category": request.category,
            "timeframe": request.timeframe,
            "is_active": True,
        }).execute()
    if not row.data:
        raise HTTPException(status_code=500, detail="Failed to create goal")
    return row.data[0]


@router.post("/preview-schedule")
def preview_milestone_schedule(request: MilestonePreviewRequest):
    """Preview how milestones would distribute across the forecast horizon."""
    profile = _load_profile(request.user_id)
    landscape = forecast_energy_landscape(supabase, request.user_id, profile)
    scheduled = assign_milestones_to_days(request.milestones, landscape)
    return {"milestones": scheduled, "landscape": landscape}


@router.post("/{goal_id}/plan")
def plan_goal_milestones(goal_id: str, request: GoalPlanRequest):
    """Insert user-approved milestones with multi-day scheduling."""
    goal_resp = (
        supabase.table("goals")
        .select("*")
        .eq("id", goal_id)
        .eq("user_id", request.user_id)
        .single()
        .execute()
    )
    if not goal_resp.data:
        raise HTTPException(status_code=404, detail="Goal not found")

    try:
        existing = (
            supabase.table("milestones")
            .select("id")
            .eq("goal_id", goal_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            raise HTTPException(status_code=400, detail="Goal already has milestones planned")
    except HTTPException:
        raise
    except Exception:
        try:
            legacy = (
                supabase.table("tasks")
                .select("id")
                .eq("goal_id", goal_id)
                .eq("is_milestone", True)
                .limit(1)
                .execute()
            )
            if legacy.data:
                raise HTTPException(status_code=400, detail="Goal already has milestones planned")
        except HTTPException:
            raise
        except Exception:
            pass

    profile = _load_profile(request.user_id)
    result = insert_scheduled_milestones(
        supabase,
        request.user_id,
        goal_id,
        request.milestones,
        profile,
        goal_title=goal_resp.data.get("title"),
    )
    return result


@router.post("/{goal_id}/decompose")
def decompose_goal_route(goal_id: str, user_id: str):
    """Generate milestone proposals for an existing goal."""
    goal_resp = (
        supabase.table("goals")
        .select("*")
        .eq("id", goal_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not goal_resp.data:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal = goal_resp.data
    profile = _load_profile(user_id)
    milestones, ai_fallback = decompose_goal(
        goal["title"],
        goal.get("category") or "work",
        goal.get("timeframe") or "3_months",
        profile,
    )
    landscape = forecast_energy_landscape(supabase, user_id, profile)
    scheduled = assign_milestones_to_days(milestones, landscape)
    return {
        "goal_id": goal_id,
        "goal_title": goal["title"],
        "milestones": scheduled,
        "landscape": landscape,
        "ai_fallback": ai_fallback,
    }
