"""Project Memory planning agent.

Turns messy project context into retrievable memory, then produces grounded,
energy-aware milestones for the existing Freeside review/confirm flow.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from supabase import Client

from services import model_router
from services.embeddings import embed_text

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 1800
CHUNK_OVERLAP_CHARS = 180


def chunk_project_context(
    text: str,
    *,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Split source text into semantic-ish chunks without external deps."""
    content = re.sub(r"\s+\n", "\n", (text or "").strip())
    content = re.sub(r"\n{3,}", "\n\n", content)
    if not content:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(paragraph):
                chunk = paragraph[start:start + max_chars].strip()
                if chunk:
                    chunks.append(chunk)
                start += max(1, max_chars - overlap_chars)
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            tail = current[-overlap_chars:].strip() if overlap_chars and current else ""
            current = f"{tail}\n\n{paragraph}".strip() if tail else paragraph

    if current:
        chunks.append(current.strip())
    return chunks


def _source_ref(row: dict) -> str:
    title = str(row.get("title") or "Project memory").strip()
    idx = row.get("chunk_index")
    return f"{title} #{idx}" if idx is not None else title


def _load_profile(db: Client, user_id: str) -> dict:
    try:
        return (
            db.table("profiles")
            .select("name, role, work_style, peak_focus_time, daily_work_hours")
            .eq("id", user_id)
            .single()
            .execute()
            .data
        ) or {}
    except Exception:
        return {}


def _latest_energy(db: Client, user_id: str) -> dict | None:
    try:
        rows = (
            db.table("energy_logs")
            .select("confirmed_score, confirmed_level, logged_at")
            .eq("user_id", user_id)
            .order("logged_at", desc=True)
            .limit(1)
            .execute()
            .data
        ) or []
        return rows[0] if rows else None
    except Exception:
        return None


def store_project_memory(
    db: Client,
    user_id: str,
    *,
    title: str,
    content: str,
    source_type: str = "project_note",
    metadata: dict | None = None,
) -> dict:
    """Chunk, embed, and insert a project memory source."""
    clean_title = (title or "").strip()[:160] or "Untitled project note"
    clean_content = (content or "").strip()
    chunks = chunk_project_context(clean_content)
    if not chunks:
        return {"inserted": 0, "chunks": []}

    inserted: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for index, chunk in enumerate(chunks):
        embedding = None
        try:
            embedding = embed_text(f"Title: {clean_title}\nSource: {source_type}\n\n{chunk}")
        except Exception as exc:  # noqa: BLE001 - memory can still be saved
            logger.warning("Project memory embedding failed: %s", str(exc)[:200])

        payload = {
            "user_id": user_id,
            "title": clean_title,
            "source_type": source_type,
            "content": chunk,
            "chunk_index": index,
            "metadata": metadata or {},
            "embedding": embedding,
            "created_at": now,
        }
        row = db.table("project_memory_sources").insert(payload).execute()
        if row.data:
            inserted.append(row.data[0])

    return {"inserted": len(inserted), "chunks": inserted}


def list_project_memory(db: Client, user_id: str, *, limit: int = 12) -> list[dict]:
    rows = (
        db.table("project_memory_sources")
        .select("id, title, source_type, content, chunk_index, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(max(1, min(limit, 50)))
        .execute()
        .data
    ) or []
    return rows


def retrieve_project_memory(
    db: Client,
    user_id: str,
    query: str,
    *,
    k: int = 6,
) -> list[dict]:
    """Semantic retrieval with recent-memory fallback when embeddings are absent."""
    clean_query = (query or "").strip()
    if not clean_query:
        return list_project_memory(db, user_id, limit=k)

    try:
        embedding = embed_text(clean_query)
        rows = (
            db.rpc(
                "match_project_memory",
                {
                    "p_user_id": user_id,
                    "p_embedding": embedding,
                    "p_match_count": k,
                },
            )
            .execute()
            .data
        ) or []
    except Exception as exc:  # noqa: BLE001 - planner can fall back to recency
        logger.warning("Project memory retrieval failed user_id=%s: %s", user_id, str(exc)[:200])
        rows = []

    if rows:
        return rows[:k]
    return list_project_memory(db, user_id, limit=k)


def _fallback_plan(question: str, retrieved: list[dict], energy_score: int) -> dict:
    load = 4 if energy_score <= 3 else 6 if energy_score <= 6 else 8
    minutes = 45 if energy_score <= 3 else 75 if energy_score <= 6 else 105
    refs = [_source_ref(row) for row in retrieved[:2]]
    topic = (question or "Project work").strip().rstrip(".")[:80]
    return {
        "reply": "I found project context and built a conservative plan you can review.",
        "milestones": [
            {
                "title": f"Clarify next deliverable for {topic}",
                "cognitive_load_score": max(2, load - 1),
                "estimated_minutes": minutes,
                "source_refs": refs,
                "tasks": [
                    {
                        "title": "Extract concrete requirements from project memory",
                        "cognitive_load_score": max(1, load - 2),
                        "estimated_minutes": 25,
                        "source_refs": refs,
                    },
                    {
                        "title": "Draft the next visible deliverable",
                        "cognitive_load_score": load,
                        "estimated_minutes": minutes,
                        "source_refs": refs,
                    },
                ],
            }
        ],
        "blockers": ["Review source context before approving if requirements changed."],
        "citations": refs,
        "ai_fallback": True,
    }


def _normalize_plan(data: dict, retrieved: list[dict]) -> dict:
    citations = [str(c).strip()[:160] for c in data.get("citations") or [] if str(c).strip()]
    if not citations:
        citations = [_source_ref(row) for row in retrieved[:4]]

    milestones: list[dict] = []
    for milestone in data.get("milestones") or []:
        if not isinstance(milestone, dict) or not milestone.get("title"):
            continue
        tasks = []
        for task in milestone.get("tasks") or []:
            if not isinstance(task, dict) or not task.get("title"):
                continue
            tasks.append({
                "title": str(task["title"]).strip()[:160],
                "cognitive_load_score": max(1, min(10, int(task.get("cognitive_load_score") or 5))),
                "estimated_minutes": max(5, min(240, int(task.get("estimated_minutes") or 30))),
                "source_refs": [str(r).strip()[:160] for r in task.get("source_refs") or [] if str(r).strip()],
            })
        if not tasks:
            tasks = [{
                "title": str(milestone["title"]).strip()[:160],
                "cognitive_load_score": max(1, min(10, int(milestone.get("cognitive_load_score") or 5))),
                "estimated_minutes": max(15, min(240, int(milestone.get("estimated_minutes") or 45))),
                "source_refs": [str(r).strip()[:160] for r in milestone.get("source_refs") or [] if str(r).strip()],
            }]
        milestones.append({
            "title": str(milestone["title"]).strip()[:160],
            "cognitive_load_score": max(1, min(10, int(milestone.get("cognitive_load_score") or 5))),
            "estimated_minutes": max(15, min(480, int(milestone.get("estimated_minutes") or sum(t["estimated_minutes"] for t in tasks)))),
            "source_refs": [str(r).strip()[:160] for r in milestone.get("source_refs") or [] if str(r).strip()],
            "tasks": tasks[:5],
        })

    return {
        "reply": str(data.get("reply") or "I drafted a grounded project plan.").strip(),
        "milestones": milestones[:4],
        "blockers": [str(b).strip()[:180] for b in data.get("blockers") or [] if str(b).strip()][:5],
        "citations": citations[:6],
        "ai_fallback": bool(data.get("ai_fallback", False)),
    }


def plan_from_project_memory(
    db: Client,
    user_id: str,
    *,
    question: str,
    energy_score: int | None = None,
    energy_level: str | None = None,
) -> dict:
    """Retrieve project context and produce reviewable Freeside milestones."""
    profile = _load_profile(db, user_id)
    latest_energy = _latest_energy(db, user_id)
    score = int(energy_score or (latest_energy or {}).get("confirmed_score") or 5)
    score = max(1, min(10, score))
    level = energy_level or (latest_energy or {}).get("confirmed_level") or (
        "high" if score >= 7 else "balanced" if score >= 4 else "low"
    )
    retrieved = retrieve_project_memory(db, user_id, question, k=6)

    if not retrieved:
        return {
            "reply": "Add project notes first so I can ground the plan in real context.",
            "milestones": [],
            "blockers": ["No project memory has been saved yet."],
            "citations": [],
            "retrieved_context": [],
            "ai_fallback": True,
        }

    context_lines = []
    for i, row in enumerate(retrieved, 1):
        ref = _source_ref(row)
        context_lines.append(
            f"[{ref}]\n"
            f"source_type: {row.get('source_type') or 'project_note'}\n"
            f"content: {str(row.get('content') or '')[:1400]}"
        )

    prompt = f"""You are Freeside's Project Memory & Planning Agent.

Audience: freelancers, students, founders, and knowledge workers with messy,
real work context and fluctuating cognitive energy.

USER PROFILE:
- Role: {profile.get('role', 'knowledge worker')}
- Work style: {profile.get('work_style', 'unknown')}
- Peak focus: {profile.get('peak_focus_time', 'unknown')}
- Daily focused hours: {profile.get('daily_work_hours', 'unknown')}
- Current energy: {level} ({score}/10)

USER REQUEST:
{question}

RETRIEVED PROJECT MEMORY:
{chr(10).join(context_lines)}

Create 1-3 milestones and 2-4 child tasks per milestone that directly advance
the user's project. Ground every milestone in retrieved memory. Match cognitive
load to current energy:
- low energy (1-3): mostly load 1-4, tiny setup/review/admin steps
- balanced (4-6): load 3-6, one moderate creation step
- high (7-10): load 6-9, deep work is allowed

Each task must be concrete, verb-first, and useful today. Add blockers when
source context is ambiguous or missing. Use source_refs that exactly match the
bracket labels from retrieved memory.

Respond ONLY as JSON:
{{
  "reply": "<one short paragraph>",
  "milestones": [
    {{
      "title": "<verb-first milestone>",
      "cognitive_load_score": <1-10>,
      "estimated_minutes": <15-480>,
      "source_refs": ["<source ref>"],
      "tasks": [
        {{
          "title": "<verb-first task>",
          "cognitive_load_score": <1-10>,
          "estimated_minutes": <5-240>,
          "source_refs": ["<source ref>"]
        }}
      ]
    }}
  ],
  "blockers": ["<missing info or risk>"],
  "citations": ["<source ref>"]
}}"""

    try:
        data = model_router.generate_json("project_memory_plan", contents=prompt, user_id=user_id)
        plan = _normalize_plan(data, retrieved)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Project memory plan failed user_id=%s: %s", user_id, str(exc)[:200])
        plan = _fallback_plan(question, retrieved, score)

    return {
        **plan,
        "retrieved_context": [
            {
                "id": row.get("memory_id") or row.get("id"),
                "title": row.get("title"),
                "source_type": row.get("source_type"),
                "chunk_index": row.get("chunk_index"),
                "similarity": row.get("similarity"),
                "preview": str(row.get("content") or "")[:260],
            }
            for row in retrieved
        ],
    }
