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
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

try:
    from google import genai
    from google.genai import types
    _GEMINI_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - exercised in minimal CI envs
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    _GEMINI_IMPORT_ERROR = exc

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

# Providers
GEMINI = "gemini"
ANTHROPIC = "anthropic"

_gemini_client = (
    genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    if genai is not None
    else None
)


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
    "project_memory_plan": ModelSpec(GEMINI, "gemini-2.5-flash", 0.4, 1200),
    # Open-ended chat / agentic → Sonnet tier in the plan.
    "copilot_chat":     ModelSpec(GEMINI, "gemini-2.5-flash", 0.7, 1000),         # target: claude-sonnet-4.6
    "copilot_action":   ModelSpec(GEMINI, "gemini-2.5-flash", 0.4, 800),          # target: claude-sonnet-4.6
}

DEFAULT_SPEC = ModelSpec(GEMINI, "gemini-2.5-flash")


class ModelResponseError(Exception):
    """Raised when a model response cannot satisfy the expected contract."""

    def __init__(
        self,
        task_type: str,
        message: str,
        *,
        cause: Exception | None = None,
        raw_response: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.task_type = task_type
        self.message = message
        self.cause = cause
        self.raw_response = raw_response


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class EnergyInferenceResponse(_StrictModel):
    suggested_score: int = Field(ge=1, le=10)
    suggested_level: Literal["high", "balanced", "low"]
    reasoning: str = Field(min_length=1)


class TaskSpecResponse(_StrictModel):
    title: str = Field(min_length=1)
    cognitive_load_score: int = Field(ge=1, le=10)
    estimated_minutes: int | None = Field(default=None, ge=1, le=480)
    reasoning: str | None = None


class BrainDumpTaskResponse(_StrictModel):
    title: str = Field(min_length=1)
    cognitive_load_score: int = Field(ge=1, le=10)


class MicroStepResponse(_StrictModel):
    text: str | None = None
    title: str | None = None
    step: str | None = None

    @model_validator(mode="after")
    def _has_step_text(self) -> "MicroStepResponse":
        if not (self.text or self.title or self.step):
            raise ValueError("micro-step response requires text, title, or step")
        return self


class TaskSplitResponse(_StrictModel):
    title: str = Field(min_length=1)
    cognitive_load_score: int = Field(ge=1, le=10)
    step_order: int = Field(ge=1, le=20)


class ProjectPlanTaskResponse(_StrictModel):
    title: str = Field(min_length=1)
    cognitive_load_score: int = Field(ge=1, le=10)
    estimated_minutes: int = Field(ge=5, le=240)
    source_refs: list[str] = Field(default_factory=list)


class ProjectPlanMilestoneResponse(_StrictModel):
    title: str = Field(min_length=1)
    cognitive_load_score: int = Field(ge=1, le=10)
    estimated_minutes: int = Field(ge=15, le=480)
    source_refs: list[str] = Field(default_factory=list)
    tasks: list[ProjectPlanTaskResponse] = Field(default_factory=list)


class ProjectMemoryPlanResponse(_StrictModel):
    reply: str = Field(min_length=1)
    milestones: list[ProjectPlanMilestoneResponse] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


JSON_OBJECT_SCHEMAS: dict[str, type[BaseModel]] = {
    "energy_inference": EnergyInferenceResponse,
    "project_memory_plan": ProjectMemoryPlanResponse,
}

JSON_ARRAY_SCHEMAS: dict[str, type[BaseModel]] = {
    "goal_decompose": TaskSpecResponse,
    "brain_dump_parse": BrainDumpTaskResponse,
    "micro_step": MicroStepResponse,
    "task_split": TaskSplitResponse,
}

JSON_CONTRACT_HINTS: dict[str, str] = {
    "energy_inference": (
        '{"suggested_score": integer 1-10, '
        '"suggested_level": "high"|"balanced"|"low", '
        '"reasoning": non-empty string}'
    ),
    "goal_decompose": (
        '[{"title": non-empty string, "cognitive_load_score": integer 1-10, '
        '"estimated_minutes": integer minutes, "reasoning": optional string}]'
    ),
    "brain_dump_parse": (
        '[{"title": non-empty string, "cognitive_load_score": integer 1-10}]'
    ),
    "micro_step": (
        '[{"text": non-empty string}]'
    ),
    "task_split": (
        '[{"title": non-empty string, "cognitive_load_score": integer 1-10, '
        '"step_order": integer >= 1}]'
    ),
    "project_memory_plan": (
        '{"reply": string, "milestones": [{"title": string, '
        '"cognitive_load_score": integer 1-10, "estimated_minutes": integer, '
        '"source_refs": [string], "tasks": [{"title": string, '
        '"cognitive_load_score": integer 1-10, "estimated_minutes": integer, '
        '"source_refs": [string]}]}], "blockers": [string], "citations": [string]}'
    ),
}


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
    if _GEMINI_IMPORT_ERROR is not None or _gemini_client is None or types is None:
        raise RuntimeError(
            "Gemini provider is not available. Install google-genai and set GEMINI_API_KEY."
        ) from _GEMINI_IMPORT_ERROR

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


def _strict_retry_contents(contents: Any, task_type: str) -> str:
    hint = JSON_CONTRACT_HINTS.get(task_type, "valid JSON for this task")
    return (
        f"{contents}\n\n"
        "Return ONLY valid JSON matching this shape: "
        f"{hint}. Do not include markdown fences, comments, or prose."
    )


def _validate_object(task_type: str, data: dict) -> dict:
    schema = JSON_OBJECT_SCHEMAS.get(task_type)
    if schema is None:
        return data
    try:
        return schema.model_validate(data).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise ModelResponseError(
            task_type,
            f"Model response failed {task_type} schema validation.",
            cause=exc,
            raw_response=data,
        ) from exc


def _validate_array(task_type: str, data: list) -> list:
    schema = JSON_ARRAY_SCHEMAS.get(task_type)
    if schema is None:
        return data
    validated = []
    try:
        for item in data:
            validated.append(schema.model_validate(item).model_dump(exclude_none=True))
        return validated
    except ValidationError as exc:
        raise ModelResponseError(
            task_type,
            f"Model response failed {task_type} array schema validation.",
            cause=exc,
            raw_response=data,
        ) from exc


def _parse_json_object(task_type: str, text: str) -> dict:
    try:
        return _validate_object(task_type, extract_json(text))
    except ModelResponseError:
        raise
    except Exception as exc:
        raise ModelResponseError(
            task_type,
            f"Model response was not valid JSON for {task_type}.",
            cause=exc,
            raw_response=text,
        ) from exc


def _parse_json_array(task_type: str, text: str) -> list:
    try:
        return _validate_array(task_type, extract_json_array(text))
    except ModelResponseError:
        raise
    except Exception as exc:
        raise ModelResponseError(
            task_type,
            f"Model response was not a valid JSON array for {task_type}.",
            cause=exc,
            raw_response=text,
        ) from exc


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
            if isinstance(exc, NotImplementedError):
                exc = ModelResponseError(
                    task_type,
                    str(exc),
                    cause=exc,
                )
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
                    if isinstance(fb_exc, NotImplementedError):
                        exc = ModelResponseError(
                            task_type,
                            str(fb_exc),
                            cause=fb_exc,
                        )
                    else:
                        exc = fb_exc
            _log_usage(
                task_type=task_type, spec=spec, tokens_in=None, tokens_out=None,
                latency_ms=int((time.perf_counter() - started) * 1000),
                cache_hit=False, ok=False, error=str(exc), user_id=user_id,
            )
            raise exc


def generate_json(
    task_type: str,
    *,
    contents: Any,
    system_instruction: str | None = None,
    response_schema: Any | None = None,
    user_id: str | None = None,
) -> dict:
    """Route a call, parse JSON, validate it, and retry once on bad shape."""
    text = generate_text(
        task_type,
        contents=contents,
        system_instruction=system_instruction,
        response_schema=response_schema,
        user_id=user_id,
    )
    try:
        return _parse_json_object(task_type, text)
    except ModelResponseError as first_error:
        retry_text = generate_text(
            task_type,
            contents=_strict_retry_contents(contents, task_type),
            system_instruction=system_instruction,
            response_schema=response_schema,
            user_id=user_id,
            retries=0,
        )
        try:
            return _parse_json_object(task_type, retry_text)
        except ModelResponseError as second_error:
            raise ModelResponseError(
                task_type,
                f"Model response for {task_type} failed validation after one retry.",
                cause=second_error,
                raw_response={
                    "first": first_error.raw_response,
                    "retry": second_error.raw_response,
                },
            ) from second_error


def generate_json_array(
    task_type: str,
    *,
    contents: Any,
    system_instruction: str | None = None,
    response_schema: Any | None = None,
    user_id: str | None = None,
) -> list:
    """Route a call, parse JSON array, validate it, and retry once on bad shape."""
    text = generate_text(
        task_type,
        contents=contents,
        system_instruction=system_instruction,
        response_schema=response_schema,
        user_id=user_id,
    )
    try:
        return _parse_json_array(task_type, text)
    except ModelResponseError as first_error:
        retry_text = generate_text(
            task_type,
            contents=_strict_retry_contents(contents, task_type),
            system_instruction=system_instruction,
            response_schema=response_schema,
            user_id=user_id,
            retries=0,
        )
        try:
            return _parse_json_array(task_type, retry_text)
        except ModelResponseError as second_error:
            raise ModelResponseError(
                task_type,
                f"Model response for {task_type} failed validation after one retry.",
                cause=second_error,
                raw_response={
                    "first": first_error.raw_response,
                    "retry": second_error.raw_response,
                },
            ) from second_error
