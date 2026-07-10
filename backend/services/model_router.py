"""
Model router (Phase 1 — Model Tiering, Structured Output, Cost Control).

A single, config-driven dispatcher between *task types* and *models*, so that
tiering decisions live in one table instead of being scattered across service
modules. Switching a tier (e.g. routing energy inference to Flash-Lite, or
Co-Pilot chat to Claude Sonnet) becomes a one-line change in TASK_MODELS.

Responsibilities:
  - Resolve task_type -> ModelSpec (provider, model, sampling params, fallback).
  - Execute the call against the right provider (Gemini today; Anthropic is
    stubbed and guarded so config can reference it before the dep is installed).
  - One bounded retry, then an optional cross-model fallback.
  - Write a cost/latency row to `ai_usage_logs` for every call (best-effort).
  - Optional structured output via Gemini `response_schema`.

Non-breaking by design: every tier currently points at the known-good Gemini
models the app already uses, so routing existing calls through here changes
behaviour only by adding logging + retry.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

# Providers
GEMINI = "gemini"
ANTHROPIC = "anthropic"

_gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))


@dataclass(frozen=True)
class ModelSpec:
    """One tier: which provider/model to use and how to sample it."""
    provider: str
    model: str
    temperature: float = 0.4
    max_output_tokens: int = 600
    thinking_budget: int = 0
    fallback: str | None = None  # a task_type to retry against on hard failure


# --- The tiering table. This is the ONE place to change a model choice. -------
# NOTE: defaults intentionally match the models the app already runs on
# (gemini-2.5-flash) so wiring existing calls through the router is a no-op
# behaviourally. The commented targets show the plan's intended cost tiers —
# flip them once the corresponding keys/deps exist and are verified.
TASK_MODELS: dict[str, ModelSpec] = {
    # Cheap, structured, high-frequency → Flash-Lite tier in the plan.
    "energy_inference": ModelSpec(GEMINI, "gemini-2.5-flash", 0.4, 300),          # target: gemini-2.5-flash-lite
    "classification":   ModelSpec(GEMINI, "gemini-2.5-flash", 0.2, 200),          # target: gemini-2.5-flash-lite
    # Medium reasoning → Flash tier.
    "goal_decompose":   ModelSpec(GEMINI, "gemini-2.5-flash", 0.4, 900),
    "brain_dump_parse": ModelSpec(GEMINI, "gemini-2.5-flash", 0.3, 600),
    "micro_step":       ModelSpec(GEMINI, "gemini-2.5-flash", 0.4, 400),
    "task_split":       ModelSpec(GEMINI, "gemini-2.5-flash", 0.4, 500),
    # Open-ended chat / agentic → Sonnet tier in the plan.
    "copilot_chat":     ModelSpec(GEMINI, "gemini-2.5-flash", 0.7, 1000),         # target: claude-sonnet-4.6
    "copilot_action":   ModelSpec(GEMINI, "gemini-2.5-flash", 0.4, 800),          # target: claude-sonnet-4.6
}

DEFAULT_SPEC = ModelSpec(GEMINI, "gemini-2.5-flash")


def resolve_spec(task_type: str) -> ModelSpec:
    """Look up the ModelSpec for a task type (falls back to a safe default)."""
    return TASK_MODELS.get(task_type, DEFAULT_SPEC)


# ---------------------------------------------------------------------------
# JSON extraction helpers (kept here to avoid a circular import with ai.py)
# ---------------------------------------------------------------------------

def extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model response:\n{text}")
    return json.loads(match.group())


def extract_json_array(text: str) -> list:
    match = re.search(r"\[.*\]", text or "", re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in model response:\n{text}")
    return json.loads(match.group())


def is_quota_error(exc: Exception) -> bool:
    s = str(exc)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()


# ---------------------------------------------------------------------------
# Usage logging (best-effort, never raises into the caller)
# ---------------------------------------------------------------------------

_supabase = None


def _get_supabase():
    global _supabase
    if _supabase is None:
        try:
            from supabase import create_client
            _supabase = create_client(
                os.getenv("SUPABASE_URL", ""),
                os.getenv("SUPABASE_SERVICE_KEY", ""),
            )
        except Exception:  # noqa: BLE001
            _supabase = False
    return _supabase or None


def _log_usage(
    *,
    task_type: str,
    spec: ModelSpec,
    tokens_in: int | None,
    tokens_out: int | None,
    latency_ms: int,
    cache_hit: bool,
    ok: bool,
    error: str | None,
    user_id: str | None,
) -> None:
    db = _get_supabase()
    if not db:
        return
    try:
        db.table("ai_usage_logs").insert({
            "user_id": user_id,
            "task_type": task_type,
            "provider": spec.provider,
            "model": spec.model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
            "cache_hit": cache_hit,
            "ok": ok,
            "error": (error or None) and error[:500],
        }).execute()
    except Exception:  # noqa: BLE001 - logging must never break a request
        pass


def _usage_tokens(response: Any) -> tuple[int | None, int | None]:
    meta = getattr(response, "usage_metadata", None)
    if not meta:
        return None, None
    return (
        getattr(meta, "prompt_token_count", None),
        getattr(meta, "candidates_token_count", None),
    )


# ---------------------------------------------------------------------------
# Provider execution
# ---------------------------------------------------------------------------

def _run_gemini(
    spec: ModelSpec,
    *,
    contents: Any,
    system_instruction: str | None,
    response_schema: Any | None,
) -> tuple[str, int | None, int | None]:
    config_kwargs: dict[str, Any] = {
        "temperature": spec.temperature,
        "max_output_tokens": spec.max_output_tokens,
        "thinking_config": types.ThinkingConfig(thinking_budget=spec.thinking_budget),
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema

    response = _gemini_client.models.generate_content(
        model=spec.model,
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    tokens_in, tokens_out = _usage_tokens(response)
    return (response.text or "").strip(), tokens_in, tokens_out


def _run_anthropic(spec: ModelSpec, **_: Any) -> tuple[str, int | None, int | None]:
    # Guarded stub: config may reference Anthropic tiers before the dependency
    # and key are set up. Wire this when Phase 2 introduces Sonnet tool-calling.
    raise NotImplementedError(
        f"Anthropic provider not configured yet (requested model '{spec.model}'). "
        "Install `anthropic`, set ANTHROPIC_API_KEY, and implement _run_anthropic."
    )


def _dispatch(
    spec: ModelSpec,
    *,
    contents: Any,
    system_instruction: str | None,
    response_schema: Any | None,
) -> tuple[str, int | None, int | None]:
    if spec.provider == GEMINI:
        return _run_gemini(
            spec,
            contents=contents,
            system_instruction=system_instruction,
            response_schema=response_schema,
        )
    if spec.provider == ANTHROPIC:
        return _run_anthropic(spec)
    raise ValueError(f"Unknown provider: {spec.provider}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_text(
    task_type: str,
    *,
    contents: Any,
    system_instruction: str | None = None,
    response_schema: Any | None = None,
    user_id: str | None = None,
    retries: int = 1,
) -> str:
    """
    Route a text-generation call by task type. Logs usage, retries once on a
    transient (non-quota) error, then tries the configured fallback tier.
    """
    spec = resolve_spec(task_type)
    attempt = 0
    started = time.perf_counter()

    while True:
        try:
            text, t_in, t_out = _dispatch(
                spec,
                contents=contents,
                system_instruction=system_instruction,
                response_schema=response_schema,
            )
            _log_usage(
                task_type=task_type, spec=spec, tokens_in=t_in, tokens_out=t_out,
                latency_ms=int((time.perf_counter() - started) * 1000),
                cache_hit=False, ok=True, error=None, user_id=user_id,
            )
            return text
        except Exception as exc:  # noqa: BLE001
            transient = not is_quota_error(exc)
            if transient and attempt < retries:
                attempt += 1
                continue
            # Try the configured fallback tier once (e.g. Gemini -> Haiku).
            if spec.fallback and spec.fallback != task_type:
                fb = resolve_spec(spec.fallback)
                try:
                    text, t_in, t_out = _dispatch(
                        fb, contents=contents,
                        system_instruction=system_instruction,
                        response_schema=response_schema,
                    )
                    _log_usage(
                        task_type=task_type, spec=fb, tokens_in=t_in, tokens_out=t_out,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        cache_hit=False, ok=True, error=f"fallback_from:{spec.model}",
                        user_id=user_id,
                    )
                    return text
                except Exception as fb_exc:  # noqa: BLE001
                    exc = fb_exc
            _log_usage(
                task_type=task_type, spec=spec, tokens_in=None, tokens_out=None,
                latency_ms=int((time.perf_counter() - started) * 1000),
                cache_hit=False, ok=False, error=str(exc), user_id=user_id,
            )
            raise


def generate_json(
    task_type: str,
    *,
    contents: Any,
    system_instruction: str | None = None,
    response_schema: Any | None = None,
    user_id: str | None = None,
) -> dict:
    """Route a call and parse the first JSON object from the response."""
    return extract_json(
        generate_text(
            task_type,
            contents=contents,
            system_instruction=system_instruction,
            response_schema=response_schema,
            user_id=user_id,
        )
    )


def generate_json_array(
    task_type: str,
    *,
    contents: Any,
    system_instruction: str | None = None,
    response_schema: Any | None = None,
    user_id: str | None = None,
) -> list:
    """Route a call and parse the first JSON array from the response."""
    return extract_json_array(
        generate_text(
            task_type,
            contents=contents,
            system_instruction=system_instruction,
            response_schema=response_schema,
            user_id=user_id,
        )
    )
