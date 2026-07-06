"""
Energy routes — AI-suggested energy inference and user confirmation.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
import logging
import os
from supabase import create_client
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from services.ai import infer_energy_from_day_context
from services.day_context import gather_day_context

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
    Returns an AI energy suggestion for today.

    Caching strategy: if the user already has an energy log today that includes
    AI reasoning (from a previous session), return that cached data without
    calling Gemini — preserves quota and is instant.
    Only calls Gemini when no cached suggestion exists for today.
    """
    today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()

    # ── Try cache first ───────────────────────────────────────────────────────
    # Fetch today's energy logs and filter in Python to avoid NULL comparison issues
    today_logs = (
        supabase.table("energy_logs")
        .select("ai_suggested_score, ai_suggested_level, ai_reasoning, calendar_event_count, calendar_context")
        .eq("user_id", user_id)
        .gte("logged_at", today_start)
        .order("logged_at", desc=True)
        .limit(5)
        .execute()
    )
    cached_log = next(
        (r for r in (today_logs.data or []) if r.get("ai_reasoning")),
        None,
    )
    if cached_log:
        return {
            "mode":                "ai_suggested",
            "ai_suggested_score":  cached_log["ai_suggested_score"],
            "ai_suggested_level":  cached_log["ai_suggested_level"],
            "reasoning":           cached_log["ai_reasoning"],
            "calendar_event_count": cached_log.get("calendar_event_count") or 0,
            "calendar_summary":    cached_log.get("calendar_context") or "",
            "from_cache":          True,
        }

    # ── No cache — fetch calendar + ClickUp + Co-Pilot, then call Gemini ───────
    profile = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )

    if not profile:
        return {"mode": "manual", "suggestion": None}

    day_context = gather_day_context(supabase, user_id, profile)

    if not day_context.get("has_any_source"):
        return {
            "mode": "manual",
            "suggestion": None,
            "calendar_not_connected": not day_context.get("calendar_connected"),
            "clickup_not_connected": not day_context.get("clickup_connected"),
        }

    try:
        suggestion = infer_energy_from_day_context(day_context, profile)

        cal = day_context.get("calendar_summary") or {}
        cu = day_context.get("clickup_summary") or {}
        return {
            "mode":                "ai_suggested",
            "ai_suggested_score":  suggestion["suggested_score"],
            "ai_suggested_level":  suggestion["suggested_level"],
            "reasoning":           suggestion["reasoning"],
            "calendar_event_count": cal.get("event_count", 0),
            "calendar_summary":    cal.get("event_list", ""),
            "clickup_task_count":  cu.get("task_count", 0),
            "clickup_overdue":     cu.get("overdue_count", 0),
            "sources_used":        day_context.get("sources_used", []),
            "from_cache":          False,
        }
    except Exception as exc:
        err_str = str(exc)
        logger.warning("Energy inference failed, falling back to manual: %s", err_str[:200])
        quota_exhausted = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
        token_expired = (
            "invalid_grant" in err_str
            or "revoked or expired" in err_str.lower()
            or "Token has been expired" in err_str
        )
        if token_expired:
            # Token is dead — clear the stale connected flag so UI can prompt reconnect.
            supabase.table("profiles").update(
                {"google_calendar_connected": False, "google_refresh_token": None}
            ).eq("id", user_id).execute()
        return {
            "mode":                      "manual",
            "suggestion":                None,
            "quota_exhausted":           quota_exhausted,
            "calendar_reconnect_required": token_expired,
            "fallback_reason":           err_str[:120],
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


@router.get("/today")
def get_today_energy(user_id: str):
    """
    Check whether the user already confirmed their energy today.
    Returns the log so the dashboard can skip the full check-in panel.
    """
    today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
    result = (
        supabase.table("energy_logs")
        .select("confirmed_score, confirmed_level, logged_at")
        .eq("user_id", user_id)
        .gte("logged_at", today_start)
        .order("logged_at", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        log = result.data[0]
        return {
            "logged_today": True,
            "confirmed_score": log["confirmed_score"],
            "confirmed_level": log["confirmed_level"],
        }
    return {"logged_today": False}
