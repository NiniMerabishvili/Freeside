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
import re
from pathlib import Path

from dotenv import load_dotenv

from prompts.freeside_copilot import FREESIDE_COPILOT_SYSTEM_PROMPT
from services.context_builder import build_context_for_user, build_freeside_context
from services import model_router

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"  # kept for reference; routing uses model_router.TASK_MODELS


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


def _detect_response_language(user_message: str, language_hint: str | None = None) -> str:
    """Choose response language from the current message, not browser locale."""
    text = user_message or ""
    if re.search(r"[\u10A0-\u10FF]", text):
        return "Georgian"
    if re.search(r"[A-Za-z]", text):
        return "English"
    if (language_hint or "").lower().startswith("ka"):
        return "Georgian"
    return "English"


def _current_message_language_directive(language: str | None, user_message: str) -> str:
    """
    Instruct the model to answer in the current message language while keeping
    machine-readable tags and field keys in English so the parser still works.
    """
    response_language = _detect_response_language(user_message, language)
    hint = f"The browser language hint is '{language}', but it is secondary. " if language else ""
    return (
        "\n\n## LANGUAGE\n"
        f"{hint}The current user message language is {response_language}. "
        "ALWAYS reply in the current user message language. This current-message "
        "language overrides browser locale, profile language, retrieved context, "
        "and previous conversation turns. If the current message is in English, "
        "reply in English. If the current message is in Georgian, reply in Georgian. "
        "Keep every XML tag name and field key in English exactly as specified "
        "(<energy_profile>, <task_card>, title:, estimated_minutes:, cognitive_weight:, "
        "proposed_date:, proposed_time_slot:, deadline:, notes:, score:, level:), "
        "but write ALL human-facing text, including task titles, notes, reasons, "
        f"and prose, in {response_language}."
    )


def _generate(
    freeside_context: str,
    user_message: str,
    conversation_history: list[dict],
    *,
    language: str | None = None,
) -> str:
    """Single model call with system prompt + injected context + history."""
    # Flatten history + context + user message into one prompt for the router.
    # (Gemini multi-turn via router is a Phase 1 follow-up; this preserves behaviour.)
    history_block = ""
    for turn in conversation_history or []:
        role = "User" if turn.get("role") == "user" else "Assistant"
        text = str(turn.get("content", "")).strip()
        if text:
            history_block += f"{role}: {text}\n"
    response_language = _detect_response_language(user_message, language)
    combined = (
        f"{history_block}\n"
        f"{freeside_context}\n\n"
        f"Reply language for this turn: {response_language}. "
        "Ignore browser locale and previous turns for language selection.\n"
        f"User message: {user_message}"
    )
    return model_router.generate_text(
        "copilot_chat",
        contents=combined,
        system_instruction=(
            FREESIDE_COPILOT_SYSTEM_PROMPT
            + _current_message_language_directive(language, user_message)
        ),
    )


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
        db, user_id, current_turn=user_message, completion_rate_7d=completion_rate_7d
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
    response_language = _detect_response_language(user_message, language)
    try:
        reply = _generate(freeside_context, user_message, conversation_history, language=language)
        if not reply:
            if response_language == "Georgian":
                return {"reply": "ახლა პასუხის შექმნა ვერ შევძელი. ცოტა ხანში სცადე თავიდან.",
                        "ai_fallback": True}
            return {"reply": "I couldn't generate a response just now — try again in a moment.",
                    "ai_fallback": True}
        return {"reply": reply, "ai_fallback": False}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Freeside Copilot chat failed: %s", str(exc)[:200])
        if _is_quota_error(exc):
            if response_language == "Georgian":
                return {
                    "reply": (
                        "ახლა დროებით მიუწვდომელი ვარ, რადგან დღევანდელი AI ლიმიტი ამოიწურა. "
                        "ხვალ ისევ იმუშავებს, ან შეგიძლია Google AI Studio-ში billing ჩართო."
                    ),
                    "ai_fallback": True,
                }
            return {
                "reply": (
                    "I'm temporarily unavailable — today's AI quota has been reached. "
                    "I'll be back tomorrow, or you can enable billing in Google AI Studio."
                ),
                "ai_fallback": True,
            }
        if response_language == "Georgian":
            return {"reply": "პასუხის გაცემა გამიჭირდა. ცოტა ხანში სცადე თავიდან.",
                    "ai_fallback": True}
        return {"reply": "I had trouble responding. Please try again in a moment.",
                "ai_fallback": True}
