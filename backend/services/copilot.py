"""
Freeside Copilot chat service (Phase 3).

Wires the system prompt (Phase 1) and the live context builder (Phase 2) into a
model call. Adapted from the plan's Anthropic example to the repo's Gemini
(google-genai) stack:

- Anthropic's `system=` maps to Gemini's `system_instruction`.
- Anthropic's `messages=[{role, content}]` maps to Gemini `contents` built from
  `types.Content(role=..., parts=[...])`, where the assistant role is "model".
- The <freeside_context> block is rebuilt fresh every turn and injected as a
  leading user turn, exactly as in the plan (context injection).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from prompts.freeside_copilot import FREESIDE_COPILOT_SYSTEM_PROMPT
from services.context_builder import build_context_for_user, build_freeside_context

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
_MODEL = "gemini-2.5-flash"


def _is_quota_error(exc: Exception) -> bool:
    s = str(exc)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()


def _language_directive(language: str | None) -> str:
    """
    Instruct the model to answer in the user's language while keeping the
    machine-readable tags/field keys in English so the parser still works.
    """
    hint = f"The user's preferred language hint is '{language}'. " if language else ""
    return (
        "\n\n## LANGUAGE\n"
        f"{hint}Detect the language the user writes in and ALWAYS reply in that same "
        "language (for example, if the user writes in Georgian, reply in Georgian). "
        "Keep every XML tag name and field key in English exactly as specified "
        "(<energy_profile>, <task_card>, title:, estimated_minutes:, cognitive_weight:, "
        "proposed_date:, proposed_time_slot:, deadline:, notes:, score:, level:), "
        "but write ALL human-facing text — task titles, notes, reasons, and prose — "
        "in the user's language."
    )


def _history_to_contents(conversation_history: list[dict]) -> list[types.Content]:
    """Convert [{role, content}] history into Gemini Content turns."""
    contents: list[types.Content] = []
    for turn in conversation_history or []:
        role = "model" if turn.get("role") == "assistant" else "user"
        text = str(turn.get("content", ""))
        if not text:
            continue
        contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    return contents


def _generate(
    freeside_context: str,
    user_message: str,
    conversation_history: list[dict],
    *,
    language: str | None = None,
) -> str:
    """Single Gemini call with system prompt + injected context + history."""
    contents = _history_to_contents(conversation_history)
    # Context injection: a leading user turn carrying the live XML block.
    contents.append(types.Content(role="user", parts=[types.Part(text=freeside_context)]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    response = _client.models.generate_content(
        model=_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=FREESIDE_COPILOT_SYSTEM_PROMPT + _language_directive(language),
            max_output_tokens=1000,
            temperature=0.7,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return (response.text or "").strip()


def chat_with_copilot(
    user_message: str,
    conversation_history: list[dict],
    user_profile: dict,
    auth_context: dict,
) -> tuple[str, list[dict]]:
    """
    Plan-faithful entry point.

    auth_context keys (all optional except the integrations you want live):
      - google_credentials: refresh token (str) or Credentials object
      - clickup_token, clickup_team_id, clickup_user_id
      - energy_history: list
      - overdue_count: int | None
      - completion_rate_7d: float
    Returns (assistant_reply, updated_conversation_history).
    """
    freeside_context = build_freeside_context(
        user_profile=user_profile,
        credentials=auth_context.get("google_credentials"),
        clickup_token=auth_context.get("clickup_token"),
        clickup_team_id=auth_context.get("clickup_team_id"),
        energy_history=auth_context.get("energy_history", []),
        overdue_count=auth_context.get("overdue_count"),
        completion_rate_7d=auth_context.get("completion_rate_7d", 0.7),
        clickup_user_id=auth_context.get("clickup_user_id"),
    )

    reply = _run(freeside_context, user_message, conversation_history,
                 language=auth_context.get("language"))["reply"]

    conversation_history.append({"role": "user", "content": user_message})
    conversation_history.append({"role": "assistant", "content": reply})
    return reply, conversation_history


def chat_with_copilot_for_user(
    db,
    user_id: str,
    user_message: str,
    conversation_history: list[dict] | None = None,
    *,
    language: str | None = None,
    completion_rate_7d: float = 0.7,
) -> tuple[str, list[dict]]:
    """
    Repo-native entry point: build the context straight from Supabase for a
    user_id (profile + Google token + ClickUp row), then chat.
    """
    conversation_history = conversation_history or []
    result = reply_for_user(
        db, user_id, user_message, conversation_history,
        language=language, completion_rate_7d=completion_rate_7d,
    )
    reply = result["reply"]
    conversation_history.append({"role": "user", "content": user_message})
    conversation_history.append({"role": "assistant", "content": reply})
    return reply, conversation_history


def reply_for_user(
    db,
    user_id: str,
    user_message: str,
    conversation_history: list[dict] | None = None,
    *,
    language: str | None = None,
    completion_rate_7d: float = 0.7,
) -> dict:
    """
    Route-friendly entry point. Builds context from Supabase and returns the
    raw model reply (tags intact, for downstream parsing) plus a fallback flag.
    """
    freeside_context = build_context_for_user(
        db, user_id, completion_rate_7d=completion_rate_7d
    )
    return _run(freeside_context, user_message, conversation_history or [], language=language)


def _run(
    freeside_context: str,
    user_message: str,
    conversation_history: list[dict],
    *,
    language: str | None = None,
) -> dict:
    """Shared generation wrapper with graceful quota/error handling."""
    try:
        reply = _generate(freeside_context, user_message, conversation_history, language=language)
        if not reply:
            return {"reply": "I couldn't generate a response just now — try again in a moment.",
                    "ai_fallback": True}
        return {"reply": reply, "ai_fallback": False}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Freeside Copilot chat failed: %s", str(exc)[:200])
        if _is_quota_error(exc):
            return {
                "reply": (
                    "I'm temporarily unavailable — today's AI quota has been reached. "
                    "I'll be back tomorrow, or you can enable billing in Google AI Studio."
                ),
                "ai_fallback": True,
            }
        return {"reply": "I had trouble responding. Please try again in a moment.",
                "ai_fallback": True}
