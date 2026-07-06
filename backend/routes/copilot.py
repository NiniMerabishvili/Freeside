"""
Co-Pilot routes — Context-aware AI chat with micro-step generation.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import logging
import os
from supabase import create_client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from services.ai import chat_with_copilot, build_copilot_context
from services.day_context import (
    gather_day_context,
    sync_clickup_tasks_to_db,
    insert_suggested_tasks,
    set_day_plan_focus,
)

load_dotenv()

router = APIRouter()

supabase = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)


class ChatRequest(BaseModel):
    user_id: str
    message: str
    task_id: Optional[str] = None
    message_type: Optional[str] = None   # 'break_down' | 'proactive' | 'user_initiated'


class PlanDayRequest(BaseModel):
    user_id: str
    energy_score: int
    energy_level: str


@router.post("/plan-day")
def plan_day(request: PlanDayRequest):
    """
    Generate day-plan task suggestions using calendar, profile, tasks, goals,
    and recent Co-Pilot activity. Called when the user clicks Start my day.
    """
    from services.routing_log import fetch_recent_copilot_summary

    try:
        context = build_copilot_context(request.user_id, supabase)
        copilot_activity = fetch_recent_copilot_summary(supabase, request.user_id)
        day_ctx = gather_day_context(supabase, request.user_id)
        message = f"""I'm starting my day with {request.energy_level} energy ({request.energy_score}/10).

Plan my day by analysing ALL of these together:
1. Google Calendar (meetings and open blocks from context)
2. ClickUp assigned tasks (due today, overdue, priorities)
3. My Freeside pending tasks and active goals
4. Recent Co-Pilot chat activity below
5. My current energy level ({request.energy_level}, {request.energy_score}/10)

Recent Co-Pilot activity:
{copilot_activity}

Suggest 2-4 concrete tasks I should focus on today with appropriate cognitive loads (1-10).
Include ClickUp items when they fit my energy. Name tasks clearly so I can add them to Freeside.
Prioritise what fits today's calendar blocks and my productive-day description."""

        result = chat_with_copilot(context, message)
        suggested = result.get("suggested_tasks", [])

        synced_clickup = sync_clickup_tasks_to_db(
            supabase, request.user_id, day_ctx.get("clickup_summary")
        )
        inserted = insert_suggested_tasks(supabase, request.user_id, suggested)
        focus_titles = [t.get("title", "") for t in suggested if t.get("title")]
        set_day_plan_focus(request.user_id, focus_titles)

        return {
            "reply": result.get("reply", ""),
            "suggested_tasks": suggested,
            "synced_clickup_count": synced_clickup,
            "added_tasks_count": len(inserted),
            "focus_titles": focus_titles,
            "sources_used": day_ctx.get("sources_used", []),
        }
    except Exception as exc:
        logger.warning("Plan day failed: %s", str(exc)[:200])
        return {"reply": "", "suggested_tasks": []}


@router.post("/chat")
def chat(request: ChatRequest):
    """
    Context-aware AI co-pilot chat.
    Builds context from user's energy, tasks, and goals before calling Gemini.
    """
    # Determine message type — used by PFI metric (breakdown frequency)
    if request.message_type:
        msg_type = request.message_type
    elif any(kw in request.message.lower() for kw in ["break", "breakdown", "micro", "steps"]):
        msg_type = "break_down"
    elif "energy is low" in request.message.lower() or "proactive" in request.message.lower():
        msg_type = "proactive"
    else:
        msg_type = "user_initiated"

    try:
        context = build_copilot_context(request.user_id, supabase)
        result  = chat_with_copilot(context, request.message)
        reply   = result["reply"]
        suggested_tasks = result.get("suggested_tasks", [])
    except Exception as exc:
        err_str = str(exc)
        logger.warning("Copilot chat failed: %s", err_str[:200])
        suggested_tasks = []
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            reply = (
                "I'm temporarily unavailable — the AI quota for today has been reached. "
                "I'll be back tomorrow, or you can enable billing in Google AI Studio to continue. "
                "In the meantime, you can still manage tasks and set your energy manually."
            )
        else:
            reply = "I had trouble responding. Please check that the backend is running and try again."

    # Log regardless of whether the AI call succeeded
    try:
        supabase.table("copilot_logs").insert({
            "user_id":      request.user_id,
            "message_type": msg_type,
            "task_id":      request.task_id,
        }).execute()
    except Exception:
        pass

    return {"reply": reply, "message_type": msg_type, "suggested_tasks": suggested_tasks}
