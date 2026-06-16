"""
Co-Pilot routes — Context-aware AI chat with micro-step generation.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import os
from supabase import create_client
from dotenv import load_dotenv

from services.ai import chat_with_copilot, build_copilot_context

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


@router.post("/chat")
def chat(request: ChatRequest):
    """
    Context-aware AI co-pilot chat.
    Builds context from user's energy, tasks, and goals before calling Claude.
    """
    # Build context from database
    context = build_copilot_context(request.user_id, supabase)

    # Get AI response
    reply = chat_with_copilot(context, request.message)

    # Log the interaction
    supabase.table("copilot_logs").insert(
        {
            "user_id": request.user_id,
            "message_type": "micro_step" if "break" in request.message.lower() else "user_initiated",
            "task_id": request.task_id,
        }
    ).execute()

    return {"reply": reply}
