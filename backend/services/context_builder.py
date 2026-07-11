"""
Freeside Copilot context builder (Phase 2).

Fetches live data (Google Calendar + ClickUp), computes today's metrics, and
assembles the <freeside_context> XML block injected before every model call.

Adapted to the Freeside repo conventions:
- Google Calendar auth uses a vault-decrypted refresh token, not a raw
  Credentials object.
- ClickUp uses httpx via the helpers in services/clickup.py (not requests).
- Timezone handling uses the stdlib (no pytz dependency).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from services.clickup import CLICKUP_API, PRIORITY_LABEL, _headers, verify_token
from services.embeddings import embed_text
from services.token_vault import get_api_token, get_google_refresh_token

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------

def _parse_dt(value: str | None) -> datetime | None:
    """
    Parse a Google Calendar start/end value into an aware datetime.

    Handles both timed events ('2026-07-10T09:00:00+04:00' / '...Z') and
    all-day dates ('2026-07-10', treated as midnight UTC). Returns None on
    anything unparseable.
    """
    if not value:
        return None
    raw = value.strip()
    try:
        # Python's fromisoformat handles 'Z' from 3.11+, but normalise to be safe.
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_all_day(value: str | None) -> bool:
    """All-day events come back as a bare 'YYYY-MM-DD' date with no time."""
    return bool(value) and "T" not in value


# ---------------------------------------------------------------------------
# Step 1 — Calendar fetcher
# ---------------------------------------------------------------------------

def _credentials_from_refresh_token(refresh_token: str) -> Credentials:
    """Build refreshed Google credentials from a stored refresh token."""
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    )
    creds.refresh(Request())
    return creds


def fetch_calendar_events(credentials: str | Credentials, days: int = 7) -> list[dict]:
    """
    Fetch upcoming Google Calendar events and normalise them for the context.

    `credentials` may be a stored refresh token (str) or an already-built
    google.oauth2.credentials.Credentials object.
    """
    creds = (
        _credentials_from_refresh_token(credentials)
        if isinstance(credentials, str)
        else credentials
    )
    service = build("calendar", "v3", credentials=creds)

    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days)).isoformat()

    result = (
        service.events()  # type: ignore[attr-defined]
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events: list[dict] = []
    for e in result.get("items", []):
        start = e["start"].get("dateTime", e["start"].get("date"))
        end_time = e["end"].get("dateTime", e["end"].get("date"))
        attendees = e.get("attendees", [])

        title_lower = (e.get("summary") or "").lower()
        if len(attendees) >= 2:
            event_type = "meeting"
        elif any(k in title_lower for k in ("focus", "deep work", "block")):
            event_type = "focus"
        elif any(k in title_lower for k in ("deadline", "due")):
            event_type = "deadline"
        else:
            event_type = "personal"

        events.append({
            "id": e["id"],
            "title": e.get("summary", "Untitled"),
            "start": start,
            "end": end_time,
            "attendees_count": len(attendees),
            "all_day": _is_all_day(start),
            "type": event_type,
        })

    return events


# ---------------------------------------------------------------------------
# Step 2 — ClickUp fetcher
# ---------------------------------------------------------------------------

def fetch_clickup_tasks(
    api_token: str,
    team_id: str,
    *,
    clickup_user_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    Fetch open, assigned ClickUp tasks with due dates and normalise them.

    Mirrors the fields the Copilot context needs. Uses httpx + the shared
    auth header helper (personal pk_ tokens vs OAuth Bearer) from
    services/clickup.py. Resolves the ClickUp user id when not supplied.
    """
    if clickup_user_id is None:
        user = verify_token(api_token)
        clickup_user_id = int(user["id"])

    params: dict[str, Any] = {
        "assignees[]": clickup_user_id,
        "include_closed": "false",
        "subtasks": "true",
        "order_by": "due_date",
        "reverse": "false",
    }

    with httpx.Client(timeout=25) as client:
        response = client.get(
            f"{CLICKUP_API}/team/{team_id}/task",
            headers=_headers(api_token),
            params=params,
        )
        response.raise_for_status()
        raw_tasks = response.json().get("tasks", [])

    tasks: list[dict] = []
    for t in raw_tasks[:limit]:
        # Duration from time_estimate (ms) or a 60-minute default.
        estimated_ms = t.get("time_estimate") or 3_600_000
        try:
            estimated_minutes = int(estimated_ms) // 60_000
        except (TypeError, ValueError):
            estimated_minutes = 60

        priority = t.get("priority")
        pri_id = priority.get("id") if isinstance(priority, dict) else priority
        try:
            priority_value = int(pri_id) if pri_id is not None else 3
        except (TypeError, ValueError):
            priority_value = 3

        tasks.append({
            "id": t.get("id"),
            "title": t.get("name", "Untitled"),
            "priority": priority_value,
            "priority_label": PRIORITY_LABEL.get(pri_id if isinstance(pri_id, int) else None, "normal"),
            "estimated_minutes": estimated_minutes,
            "due_date": t.get("due_date"),
            "status": (t.get("status") or {}).get("status", "open"),
            "tags": [tag.get("name") for tag in t.get("tags", []) if tag.get("name")],
            "list_name": (t.get("list") or {}).get("name", ""),
        })

    return tasks


def _count_overdue(clickup_tasks: list[dict]) -> int:
    """Count ClickUp tasks whose due date is strictly in the past."""
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    overdue = 0
    for t in clickup_tasks:
        due = t.get("due_date")
        if not due:
            continue
        try:
            if int(due) < now_ms:
                overdue += 1
        except (TypeError, ValueError):
            continue
    return overdue


# ---------------------------------------------------------------------------
# Step 3 — Today's metrics
# ---------------------------------------------------------------------------

def compute_today_metrics(calendar_events: list[dict]) -> dict:
    """
    Compute the day-shape signals the Copilot uses to route work:
    meeting count/minutes, fragmentation, and available focus blocks.

    Only timed events count; all-day markers (holidays, birthdays) are ignored.
    """
    today = date.today().isoformat()
    today_events = [
        e for e in calendar_events
        if not e.get("all_day")
        and e.get("start")
        and str(e["start"]).startswith(today)
    ]

    meeting_events = [e for e in today_events if e["type"] == "meeting"]
    meeting_count = len(meeting_events)

    meeting_minutes = 0
    for e in meeting_events:
        start = _parse_dt(e["start"])
        end = _parse_dt(e["end"])
        if start and end:
            meeting_minutes += max(0, int((end - start).total_seconds() / 60))

    # Fragmentation: many short gaps between events break up the day.
    gaps: list[float] = []
    sorted_events = sorted(
        (e for e in today_events if _parse_dt(e["start"]) and _parse_dt(e["end"])),
        key=lambda x: _parse_dt(x["start"]),  # type: ignore[arg-type,return-value]
    )
    for i in range(1, len(sorted_events)):
        prev_end = _parse_dt(sorted_events[i - 1]["end"])
        curr_start = _parse_dt(sorted_events[i]["start"])
        if not prev_end or not curr_start:
            continue
        gap_min = (curr_start - prev_end).total_seconds() / 60
        if 0 < gap_min < 90:
            gaps.append(gap_min)

    fragmentation_score = min(100, len(gaps) * 15)
    focus_blocks = sum(1 for g in gaps if g >= 45)

    return {
        "meeting_count": meeting_count,
        "meeting_minutes_total": meeting_minutes,
        "fragmentation_score": fragmentation_score,
        "focus_blocks_available": focus_blocks,
    }


# ---------------------------------------------------------------------------
# Step 4 — Assemble the context XML
# ---------------------------------------------------------------------------

def _profile_view(user_profile: dict) -> dict:
    """
    Map the stored Freeside profile onto the fields the Copilot expects,
    keeping the plan's field names with sensible fallbacks.
    """
    peak = user_profile.get("peak_focus_time")
    chronotype = user_profile.get("chronotype") or (
        {"morning": "early", "evening": "late"}.get(peak, "neutral")
    )
    return {
        "name": user_profile.get("name", "User"),
        "chronotype": chronotype,
        "work_hours": user_profile.get("work_hours", {"start": "09:00", "end": "18:00"}),
        "deep_work_slots": user_profile.get(
            "deep_work_slots",
            [peak] if peak else ["09:00–11:00"],
        ),
        "task_split_preference": user_profile.get("task_split_preference", "confirm"),
    }


def build_freeside_context(
    user_profile: dict,
    credentials: str | Credentials | None,
    clickup_token: str | None,
    clickup_team_id: str | None,
    energy_history: list | None = None,
    overdue_count: int | None = None,
    completion_rate_7d: float = 0.7,
    *,
    clickup_user_id: int | None = None,
    relevant_history: list[dict] | None = None,
    burnout_risk: dict | None = None,
) -> str:
    """
    Assemble the full <freeside_context> XML block.

    Any integration that is missing or fails is degraded gracefully to an empty
    list rather than raising, so the Copilot always gets a valid context block.
    """
    energy_history = energy_history or []
    relevant_history = relevant_history or []

    calendar_events: list[dict] = []
    if credentials:
        try:
            calendar_events = fetch_calendar_events(credentials)
        except Exception as exc:  # noqa: BLE001 - context must never hard-fail
            logger.warning("Calendar fetch failed: %s", str(exc)[:200])

    clickup_tasks: list[dict] = []
    if clickup_token and clickup_team_id:
        try:
            clickup_tasks = fetch_clickup_tasks(
                clickup_token, clickup_team_id, clickup_user_id=clickup_user_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ClickUp fetch failed: %s", str(exc)[:200])

    today_metrics = compute_today_metrics(calendar_events)
    if overdue_count is None:
        overdue_count = _count_overdue(clickup_tasks)
    today_metrics["overdue_task_count"] = overdue_count
    today_metrics["completion_rate_7d"] = completion_rate_7d

    profile = _profile_view(user_profile)
    burnout_block = ""
    if burnout_risk:
        if burnout_risk.get("status") == "insufficient_data":
            burnout_block = f"""
  <burnout_risk>
    status: insufficient_data
    risk_band: insufficient_data
    reason: {burnout_risk.get("reason") or "Not enough recent data yet."}
    computed_at: {burnout_risk.get("computed_at") or "unknown"}
  </burnout_risk>
"""
        else:
            burnout_block = f"""
  <burnout_risk>
    score: {burnout_risk["score"]}
    risk_band: {burnout_risk["risk_band"]}
    computed_at: {burnout_risk.get("computed_at") or "unknown"}
    model_version: {burnout_risk.get("model_version") or "unknown"}
  </burnout_risk>
"""

    context = f"""<freeside_context>
  <user_profile>
    name: {profile["name"]}
    chronotype: {profile["chronotype"]}
    typical_work_hours: {profile["work_hours"]}
    preferred_deep_work_slots: {profile["deep_work_slots"]}
    task_split_preference: {profile["task_split_preference"]}
  </user_profile>

  <current_datetime>{datetime.now().isoformat()}</current_datetime>

  <calendar_data>
{json.dumps(calendar_events, indent=4)}
  </calendar_data>

  <clickup_data>
{json.dumps(clickup_tasks, indent=4)}
  </clickup_data>

  <energy_history>
{json.dumps(energy_history, indent=4)}
  </energy_history>

  <relevant_history>
{json.dumps(relevant_history, indent=4)}
  </relevant_history>
{burnout_block}

  <today_metrics>
    meeting_count: {today_metrics["meeting_count"]}
    meeting_minutes_total: {today_metrics["meeting_minutes_total"]}
    fragmentation_score: {today_metrics["fragmentation_score"]}
    focus_blocks_available: {today_metrics["focus_blocks_available"]}
    overdue_task_count: {today_metrics["overdue_task_count"]}
    completion_rate_7d: {today_metrics["completion_rate_7d"]}
  </today_metrics>
</freeside_context>"""

    return context


# ---------------------------------------------------------------------------
# Convenience: build context straight from the DB for a given user
# ---------------------------------------------------------------------------

def _recent_energy_history(db, user_id: str, limit: int = 7) -> list[dict]:
    try:
        resp = (
            db.table("energy_logs")
            .select("logged_at, confirmed_score, confirmed_level")
            .eq("user_id", user_id)
            .order("logged_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(reversed(resp.data or []))
    except Exception:
        return []


def fetch_relevant_history(
    db,
    user_id: str,
    current_turn: str | None,
    *,
    k: int = 5,
) -> list[dict]:
    """
    Retrieve semantically relevant prior Co-Pilot turns, tasks, and goals.

    Explicitly passes user_id into the SQL function because service-role clients
    bypass RLS; the database function also filters every source table by user_id.
    """
    query = (current_turn or "").strip()
    if not query:
        return []

    try:
        embedding = embed_text(query)
        rows = (
            db.rpc(
                "match_copilot_context",
                {
                    "p_user_id": user_id,
                    "p_embedding": embedding,
                    "p_match_count": k,
                },
            )
            .execute()
            .data
        ) or []
    except Exception as exc:  # noqa: BLE001 - context should degrade, not fail chat
        logger.warning("Semantic context retrieval failed user_id=%s: %s", user_id, str(exc)[:200])
        return []

    relevant: list[dict] = []
    for row in rows[:k]:
        relevant.append({
            "source_type": row.get("source_type"),
            "source_id": row.get("source_id"),
            "title": row.get("title"),
            "content": (row.get("content") or "")[:1200],
            "similarity": row.get("similarity"),
            "created_at": row.get("created_at"),
        })
    return relevant


def _burnout_risk_band(score: float) -> str:
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "moderate"
    return "low"


def fetch_latest_burnout_risk(db, user_id: str) -> dict | None:
    """Return the latest burnout score context, or None when no score exists."""
    try:
        rows = (
            db.table("burnout_scores")
            .select("score, label, model_version, computed_at, features")
            .eq("user_id", user_id)
            .order("computed_at", desc=True)
            .limit(1)
            .execute()
            .data
        ) or []
    except Exception as exc:  # noqa: BLE001 - context should degrade, not fail chat
        logger.warning("Burnout risk fetch failed user_id=%s: %s", user_id, str(exc)[:200])
        return None

    if not rows:
        return None

    row = rows[0]
    features = row.get("features") or {}
    if isinstance(features, dict) and features.get("sufficient_data") is False:
        return {
            "status": "insufficient_data",
            "reason": features.get("insufficient_data_reason") or "Not enough recent data yet.",
            "computed_at": row.get("computed_at"),
            "model_version": row.get("model_version"),
        }

    score = row.get("score")
    if score is None:
        return None
    try:
        score_float = float(score)
    except (TypeError, ValueError):
        return None
    return {
        "status": "available",
        "score": round(score_float, 3),
        "risk_band": _burnout_risk_band(score_float),
        "computed_at": row.get("computed_at"),
        "model_version": row.get("model_version"),
    }


def build_context_for_user(
    db,
    user_id: str,
    *,
    current_turn: str | None = None,
    completion_rate_7d: float = 0.7,
) -> str:
    """
    Repo-native entry point: gather the profile, Google refresh token, and
    ClickUp integration row from Supabase, then build the context block.
    """
    profile = (
        db.table("profiles").select("*").eq("id", user_id).single().execute().data
    ) or {}

    refresh_token = (
        get_google_refresh_token(user_id, db)
        if profile.get("google_calendar_connected")
        else None
    )

    clickup_token = clickup_team_id = None
    try:
        rows = (
            db.table("user_integrations")
            .select(
                "user_id, integration_type, is_connected, context_notes, "
                "workspace_name, external_team_id, account_label, created_at, updated_at"
            )
            .eq("user_id", user_id)
            .eq("integration_type", "clickup")
            .eq("is_connected", True)
            .limit(1)
            .execute()
            .data
        ) or []
        if rows:
            clickup_token = get_api_token(user_id, db)
            clickup_team_id = rows[0].get("external_team_id")
    except Exception:
        pass

    return build_freeside_context(
        user_profile=profile,
        credentials=refresh_token,
        clickup_token=clickup_token,
        clickup_team_id=clickup_team_id,
        energy_history=_recent_energy_history(db, user_id),
        overdue_count=None,
        completion_rate_7d=completion_rate_7d,
        relevant_history=fetch_relevant_history(db, user_id, current_turn, k=5),
        burnout_risk=fetch_latest_burnout_risk(db, user_id),
    )
