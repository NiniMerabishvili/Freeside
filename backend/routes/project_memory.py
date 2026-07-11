"""Project Memory routes for grounded, energy-aware planning."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

from services.goal_planning import insert_copilot_milestones
from services.project_memory import (
    list_project_memory,
    plan_from_project_memory,
    store_project_memory,
)

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

router = APIRouter()

supabase = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)


class ProjectMemoryCreateRequest(BaseModel):
    user_id: str
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1)
    source_type: str = "project_note"
    metadata: dict | None = None


class ProjectMemoryPlanRequest(BaseModel):
    user_id: str
    question: str = Field(min_length=1, max_length=1200)
    energy_score: Optional[int] = Field(default=None, ge=1, le=10)
    energy_level: Optional[str] = None


class ProjectMemoryConfirmRequest(BaseModel):
    user_id: str
    milestones: list


def _load_profile(user_id: str) -> dict:
    try:
        return (
            supabase.table("profiles")
            .select("role, work_style, peak_focus_time, daily_work_hours")
            .eq("id", user_id)
            .single()
            .execute()
            .data
        ) or {}
    except Exception:
        return {}


@router.get("/sources")
def list_sources(user_id: str):
    """Recent project memory chunks for the user."""
    return {"sources": list_project_memory(supabase, user_id)}


@router.post("/sources")
def create_source(request: ProjectMemoryCreateRequest):
    """Save messy project context as retrievable memory chunks."""
    result = store_project_memory(
        supabase,
        request.user_id,
        title=request.title,
        content=request.content,
        source_type=request.source_type,
        metadata=request.metadata,
    )
    if result["inserted"] == 0:
        raise HTTPException(status_code=400, detail="Project memory content is empty")
    return result


@router.post("/plan")
def plan_project_memory(request: ProjectMemoryPlanRequest):
    """Generate grounded milestones from project memory for user review."""
    return plan_from_project_memory(
        supabase,
        request.user_id,
        question=request.question,
        energy_score=request.energy_score,
        energy_level=request.energy_level,
    )


@router.post("/confirm")
def confirm_project_memory_plan(request: ProjectMemoryConfirmRequest):
    """Insert user-approved Project Memory milestones into Freeside."""
    return insert_copilot_milestones(
        supabase,
        request.user_id,
        request.milestones,
        _load_profile(request.user_id),
    )
