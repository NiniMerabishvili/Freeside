"""
Co-Pilot routes — Context-aware AI chat with micro-step generation.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import os
from supabase import create_client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from services.ai import chat_with_copilot, build_copilot_context
from services.goal_planning import insert_copilot_milestones
from services.day_context import (
    gather_day_context,
    sync_clickup_tasks_to_db,
    set_day_plan_focus,
)
from services.copilot_rate_limit import RateLimitResult, copilot_rate_limiter
from services.embeddings import enqueue_copilot_turn_embedding

from services.copilot import reply_for_user
from services.copilot_actions import (
    extract_energy_profile,
    extract_task_cards,
    parse_copilot_actions,
    strip_structured_blocks,
    task_cards_to_suggestions,
)
from services.copilot_history import (
    fetch_recent_copilot_conversation,
    fetch_recent_copilot_turns,
    log_copilot_exchange,
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
    energy_score: Optional[int] = None
    energy_level: Optional[str] = None
    language: Optional[str] = None       # BCP-47 hint from the browser (e.g. 'ka', 'en-US')
    pricing_tier: str = "free"


class PlanDayRequest(BaseModel):
    user_id: str
    energy_score: int
    energy_level: str
    pricing_tier: str = "free"


def _raise_rate_limited(result: RateLimitResult) -> None:
    raise HTTPException(
        status_code=429,
        detail={
            "error": "rate_limited",
            "message": "Co-Pilot is moving a little too fast. Please try again soon.",
            "retry_after_seconds": result.retry_after_seconds,
            "reason": result.reason,
            "limit": result.limit,
            "window_seconds": result.window_seconds,
        },
        headers={"Retry-After": str(result.retry_after_seconds)},
    )


def _check_turn_limit(user_id: str, pricing_tier: str) -> None:
    result = copilot_rate_limiter.check_turn(user_id, pricing_tier)
    if not result.allowed:
        _raise_rate_limited(result)


def _check_tool_limit(user_id: str, pricing_tier: str, count: int) -> None:
    result = copilot_rate_limiter.check_tool_calls(user_id, count, pricing_tier)
    if not result.allowed:
        _raise_rate_limited(result)


@router.post("/plan-day")
def plan_day(request: PlanDayRequest):
    """
    Generate day-plan task suggestions using calendar, profile, tasks, goals,
    and recent Co-Pilot activity. Called when the user clicks Start my day.
    """
    _check_turn_limit(request.user_id, request.pricing_tier)
    try:
        context = build_copilot_context(
            request.user_id,
            supabase,
            energy_score=request.energy_score,
            energy_level=request.energy_level,
        )
        copilot_activity = fetch_recent_copilot_conversation(supabase, request.user_id)
        day_ctx = gather_day_context(supabase, request.user_id)
        message = f"""I'm starting my day with {request.energy_level} energy ({request.energy_score}/10).

Plan my day by analysing ALL of these together:
1. Google Calendar (meetings and open blocks from context)
2. ClickUp assigned tasks (due today, overdue, priorities)
3. My Freeside pending tasks and active goals
4. Recent Co-Pilot conversation below — honour what I asked to build/implement
5. My current energy level ({request.energy_level}, {request.energy_score}/10)

Recent Co-Pilot conversation:
{copilot_activity}

Create 2-4 tasks that DIRECTLY advance my active goals and what I discussed in Co-Pilot (e.g. product features, integrations, thesis work).
Do NOT suggest generic admin tasks (emails, meeting notes) unless I explicitly asked for those in chat.
Loads must fit my energy ({request.energy_score}/10): low=1-4, balanced=3-6, high=6-10.
Name tasks clearly for my Freeside task list."""

        result = chat_with_copilot(context, message)
        suggested = result.get("suggested_tasks", [])
        suggested_milestones = result.get("suggested_milestones", [])

        synced_clickup = sync_clickup_tasks_to_db(
            supabase, request.user_id, day_ctx.get("clickup_summary")
        )
        if suggested_milestones:
            _check_tool_limit(
                request.user_id,
                request.pricing_tier,
                len(suggested_milestones),
            )
            inserted_result = insert_copilot_milestones(
                supabase, request.user_id, suggested_milestones
            )
            added_count = inserted_result.get("inserted_tasks", 0)
        else:
            added_count = 0
        focus_titles = [t.get("title", "") for t in suggested if t.get("title")]
        set_day_plan_focus(request.user_id, focus_titles)

        return {
            "reply": result.get("reply", ""),
            "suggested_tasks": suggested,
            "suggested_milestones": suggested_milestones,
            "synced_clickup_count": synced_clickup,
            "added_tasks_count": added_count,
            "focus_titles": focus_titles,
            "sources_used": day_ctx.get("sources_used", []),
            "sync_warnings": day_ctx.get("sync_warnings", []),
            "ai_fallback": result.get("ai_fallback", False),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Plan day failed: %s", str(exc)[:200])
        return {"reply": "", "suggested_tasks": []}


@router.post("/chat")
def chat(request: ChatRequest):
    """
    Context-aware Freeside Copilot chat (services/copilot.py).

    Builds a live <freeside_context> block (profile + Google Calendar + ClickUp +
    energy history + today's metrics), replies in the user's language, then parses
    the structured blocks (<energy_profile>, <task_card>, reschedule/split lines)
    out of the reply so the UI can render clean, human-readable language.
    """
    # Determine message type — used by PFI metric (breakdown frequency)
    _check_turn_limit(request.user_id, request.pricing_tier)

    if request.message_type:
        msg_type = request.message_type
    elif any(kw in request.message.lower() for kw in ["break", "breakdown", "micro", "steps"]):
        msg_type = "break_down"
    elif "energy is low" in request.message.lower() or "proactive" in request.message.lower():
        msg_type = "proactive"
    else:
        msg_type = "user_initiated"

    energy_profile = None
    task_cards: list = []
    actions: list = []
    suggested_tasks: list = []

    try:
        history = fetch_recent_copilot_turns(supabase, request.user_id)
        result = reply_for_user(
            supabase,
            request.user_id,
            request.message,
            history,
            language=request.language,
        )
        raw_reply = result["reply"]
        ai_fallback = result.get("ai_fallback", False)

        if not ai_fallback:
            energy_profile = extract_energy_profile(raw_reply)
            task_cards = extract_task_cards(raw_reply)
            actions = parse_copilot_actions(raw_reply)
            _check_tool_limit(
                request.user_id,
                request.pricing_tier,
                len(task_cards) + len(actions),
            )
            suggested_tasks = task_cards_to_suggestions(task_cards)

        # Strip machine-readable blocks so the bubble shows only natural language.
        reply = strip_structured_blocks(raw_reply) or raw_reply
    except HTTPException:
        raise
    except Exception as exc:
        err_str = str(exc)
        logger.warning("Copilot chat failed: %s", err_str[:200])
        ai_fallback = True
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            reply = (
                "I'm temporarily unavailable — the AI quota for today has been reached. "
                "I'll be back tomorrow, or you can enable billing in Google AI Studio to continue. "
                "In the meantime, you can still manage tasks and set your energy manually."
            )
        else:
            reply = "I had trouble responding. Please check that the backend is running and try again."

    try:
        turn = log_copilot_exchange(
            supabase,
            user_id=request.user_id,
            message_type=msg_type,
            user_message=request.message,
            assistant_reply=reply,
            task_id=request.task_id,
            energy_level=request.energy_level,
        )
        if turn and turn.get("id"):
            enqueue_copilot_turn_embedding(supabase, turn)
    except Exception:
        pass

    return {
        "reply": reply,
        "message_type": msg_type,
        "suggested_tasks": suggested_tasks,
        "suggested_milestones": [],
        "energy_profile": energy_profile,
        "task_cards": task_cards,
        "actions": actions,
        "ai_fallback": ai_fallback,
    }
