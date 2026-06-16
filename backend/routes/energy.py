"""
Energy routes — AI-suggested energy inference and user confirmation.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import os
from supabase import create_client
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from services.calendar import get_today_events, summarize_events
from services.ai import infer_energy_from_calendar

router = APIRouter()

supabase = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)


class EnergyConfirmRequest(BaseModel):
    user_id: str
    confirmed_score: int
    confirmed_level: str
    ai_suggested_score: Optional[int] = None
    ai_suggested_level: Optional[str] = None
    ai_reasoning: Optional[str] = None
    calendar_event_count: Optional[int] = None
    calendar_context: Optional[str] = None


@router.get("/suggest")
def suggest_energy(user_id: str):
    """
    Called every morning when dashboard loads.
    Fetches calendar → runs AI inference → returns suggestion.
    """
    # Get user profile
    profile = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )

    if not profile.get("google_calendar_connected"):
        # No calendar connected — skip inference, user will set manually
        return {"mode": "manual", "suggestion": None}

    # Fetch and summarize calendar
    events = get_today_events(profile["google_refresh_token"])
    calendar_summary = summarize_events(events)

    # Run AI inference
    suggestion = infer_energy_from_calendar(calendar_summary, profile)

    return {
        "mode": "ai_suggested",
        "ai_suggested_score": suggestion["suggested_score"],
        "ai_suggested_level": suggestion["suggested_level"],
        "reasoning": suggestion["reasoning"],
        "calendar_event_count": calendar_summary["event_count"],
        "calendar_summary": calendar_summary["event_list"],
    }


@router.post("/confirm")
def confirm_energy(request: EnergyConfirmRequest):
    """Called when user confirms or adjusts the energy suggestion."""

    result = (
        supabase.table("energy_logs")
        .insert(
            {
                "user_id": request.user_id,
                "ai_suggested_score": request.ai_suggested_score,
                "ai_suggested_level": request.ai_suggested_level,
                "ai_reasoning": request.ai_reasoning,
                "confirmed_score": request.confirmed_score,
                "confirmed_level": request.confirmed_level,
                "calendar_event_count": request.calendar_event_count,
                "calendar_context": request.calendar_context,
            }
        )
        .execute()
    )

    return {"status": "confirmed", "active_energy_level": request.confirmed_level}
