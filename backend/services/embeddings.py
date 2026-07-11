"""Embedding helpers for Freeside RAG infrastructure.

This module only writes embeddings on source mutations. Retrieval/ranking is
intentionally left for the next RAG prompt.
"""
from __future__ import annotations

import logging
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

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

EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSIONS = int(os.getenv("GEMINI_EMBEDDING_DIMENSIONS", "768"))
EMBEDDING_TASK_TYPE = "RETRIEVAL_DOCUMENT"

_gemini_client = (
    genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    if genai is not None
    else None
)
_executor = ThreadPoolExecutor(max_workers=int(os.getenv("EMBEDDING_WORKERS", "2")))


class EmbeddingError(Exception):
    """Raised when Gemini cannot produce a usable embedding."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


def _normalize(values: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(v * v for v in values))
    if not magnitude:
        return values
    return [v / magnitude for v in values]


def _embedding_values(response: Any) -> list[float]:
    embeddings = getattr(response, "embeddings", None) or []
    if embeddings:
        values = getattr(embeddings[0], "values", None)
        if values:
            return [float(v) for v in values]

    embedding = getattr(response, "embedding", None)
    values = getattr(embedding, "values", None) if embedding is not None else None
    if values:
        return [float(v) for v in values]

    raise ValueError("Gemini embedding response did not include vector values.")


def embed_text(text: str) -> list[float]:
    """Embed text with Gemini and return a 768-dimensional vector."""
    content = (text or "").strip()
    if not content:
        raise EmbeddingError("Cannot embed empty text.")
    if _GEMINI_IMPORT_ERROR is not None or _gemini_client is None or types is None:
        raise EmbeddingError(
            "Gemini embedding provider is not available. Install google-genai and set GEMINI_API_KEY.",
            cause=_GEMINI_IMPORT_ERROR,
        )

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = _gemini_client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=content[:12000],
                config=types.EmbedContentConfig(
                    task_type=EMBEDDING_TASK_TYPE,
                    output_dimensionality=EMBEDDING_DIMENSIONS,
                ),
            )
            values = _embedding_values(response)
            if len(values) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Expected {EMBEDDING_DIMENSIONS} embedding dimensions, got {len(values)}."
                )
            return _normalize(values)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == 0:
                time.sleep(0.25)

    raise EmbeddingError("Gemini embedding failed after one retry.", cause=last_error)


def task_embedding_text(task: dict) -> str:
    return "\n".join(
        part
        for part in (
            f"Task: {task.get('title') or ''}",
            f"Description: {task.get('description') or ''}",
            f"Source: {task.get('source') or ''}",
            f"Status: {task.get('status') or ''}",
        )
        if part.strip()
    )


def goal_embedding_text(goal: dict) -> str:
    return "\n".join(
        part
        for part in (
            f"Goal: {goal.get('title') or ''}",
            f"Category: {goal.get('category') or ''}",
            f"Timeframe: {goal.get('timeframe') or ''}",
        )
        if part.strip()
    )


def copilot_turn_embedding_text(
    *,
    user_message: str | None,
    assistant_reply: str | None,
    message_type: str | None = None,
) -> str:
    return "\n".join(
        part
        for part in (
            f"Type: {message_type or 'chat'}",
            f"User: {user_message or ''}",
            f"Co-Pilot: {assistant_reply or ''}",
        )
        if part.strip()
    )


def upsert_task_embedding(db: Any, task: dict) -> None:
    embedding = embed_text(task_embedding_text(task))
    (
        db.table("tasks")
        .update({"embedding": embedding})
        .eq("id", task["id"])
        .eq("user_id", task["user_id"])
        .execute()
    )


def upsert_goal_embedding(db: Any, goal: dict) -> None:
    embedding = embed_text(goal_embedding_text(goal))
    (
        db.table("goals")
        .update({"embedding": embedding})
        .eq("id", goal["id"])
        .eq("user_id", goal["user_id"])
        .execute()
    )


def upsert_copilot_message_embedding(db: Any, turn: dict) -> None:
    embedding = embed_text(
        copilot_turn_embedding_text(
            user_message=turn.get("user_message"),
            assistant_reply=turn.get("assistant_reply"),
            message_type=turn.get("message_type"),
        )
    )
    (
        db.table("copilot_message_embeddings")
        .upsert(
            {
                "message_id": turn["id"],
                "user_id": turn["user_id"],
                "embedding": embedding,
                "source": "copilot_turn",
            },
            on_conflict="message_id",
        )
        .execute()
    )


def enqueue_embedding_write(fn: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    """Run an embedding write in the background and log failures."""
    future = _executor.submit(fn, *args, **kwargs)

    def _log_failure(done) -> None:
        try:
            done.result()
        except Exception as exc:  # noqa: BLE001 - background write must not break request
            logger.warning("Embedding write failed: %s", str(exc)[:300])

    future.add_done_callback(_log_failure)


def enqueue_task_completion_embedding(db: Any, task: dict) -> None:
    enqueue_embedding_write(upsert_task_embedding, db, task)


def enqueue_goal_creation_embedding(db: Any, goal: dict) -> None:
    enqueue_embedding_write(upsert_goal_embedding, db, goal)


def enqueue_copilot_turn_embedding(db: Any, turn: dict) -> None:
    enqueue_embedding_write(upsert_copilot_message_embedding, db, turn)
