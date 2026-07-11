"""Gather calendar, ClickUp, and Co-Pilot context for day planning."""
from __future__ import annotations

import logging

from services.calendar import get_today_events, summarize_events
from services.clickup import fetch_clickup_summary, format_clickup_block
from services.copilot_history import fetch_recent_copilot_conversation
from services.token_vault import get_api_token, get_google_refresh_token
from services.integration_errors import (
    CalendarSyncError,
    ClickUpAuthError,
    ClickUpSyncError,
    SyncWarning,
    SyncErrorCode,
    SYNC_ERROR_MESSAGES,
    clickup_warning_from_exception,
    calendar_warning_from_exception,
)

logger = logging.getLogger(__name__)


def _load_clickup_row(db, user_id: str) -> dict | None:
    try:
        resp = (
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
        )
        rows = resp.data or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.warning(
            "ClickUp integration lookup failed for user_id=%s: %s",
            user_id,
            str(exc)[:200],
        )
        raise ClickUpSyncError(cause=exc) from exc


def gather_day_context(db, user_id: str, profile: dict | None = None) -> dict:
    """Load all signals used for energy inference and day planning."""
    if profile is None:
        profile = (
            db.table("profiles")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
            .data
        ) or {}

    calendar_summary = None
    calendar_connected = bool(profile.get("google_calendar_connected"))
    sync_warnings: list[SyncWarning] = []
    if calendar_connected:
        try:
            refresh_token = get_google_refresh_token(user_id, db)
            if not refresh_token:
                raise CalendarSyncError(
                    SyncErrorCode.CALENDAR_NOT_CONNECTED,
                    SYNC_ERROR_MESSAGES[SyncErrorCode.CALENDAR_NOT_CONNECTED],
                )
            events = get_today_events(refresh_token)
            calendar_summary = summarize_events(events)
        except CalendarSyncError as exc:
            logger.warning(
                "Calendar sync failed for user_id=%s code=%s: %s",
                user_id,
                exc.code.value,
                str(exc.cause or exc)[:200],
            )
            sync_warnings.append(calendar_warning_from_exception(exc))
            calendar_connected = False

    clickup_row = None
    clickup_summary = None
    try:
        clickup_row = _load_clickup_row(db, user_id)
    except ClickUpSyncError as exc:
        sync_warnings.append(clickup_warning_from_exception(exc))

    api_token = get_api_token(user_id, db) if clickup_row else None
    clickup_connected = bool(clickup_row and api_token)
    if clickup_connected and clickup_row.get("external_team_id"):
        try:
            clickup_summary = fetch_clickup_summary(
                api_token,
                clickup_row.get("workspace_name"),
                team_id=clickup_row.get("external_team_id"),
            )
        except (ClickUpAuthError, ClickUpSyncError) as exc:
            logger.warning(
                "ClickUp sync failed for user_id=%s code=%s: %s",
                user_id,
                exc.code.value,
                str(exc.cause or exc)[:200],
            )
            sync_warnings.append(clickup_warning_from_exception(exc))
            clickup_summary = None

    if clickup_summary:
        clickup_block = format_clickup_block(clickup_summary)
    elif clickup_connected and clickup_row and (
        not clickup_row.get("external_team_id") and not clickup_row.get("workspace_name")
    ):
        label = clickup_row.get("account_label") or "ClickUp"
        clickup_block = f"{label} connected - workspace not selected yet."
    elif any(w.integration == "clickup" for w in sync_warnings):
        clickup_block = SYNC_ERROR_MESSAGES[SyncErrorCode.CLICKUP_FETCH_FAILED]
    else:
        clickup_block = "ClickUp not connected."

    copilot_summary = fetch_recent_copilot_conversation(db, user_id)

    has_copilot = copilot_summary and "No recent" not in copilot_summary
    has_clickup_tasks = bool(
        clickup_summary and clickup_summary.get("task_count", 0) > 0
    )
    has_calendar = calendar_summary is not None
    clickup_live = has_clickup_connected_pending(clickup_block)

    return {
        "profile": profile,
        "calendar_summary": calendar_summary,
        "calendar_connected": calendar_connected and calendar_summary is not None,
        "clickup_summary": clickup_summary,
        "clickup_row": clickup_row,
        "clickup_block": clickup_block,
        "clickup_connected": clickup_connected,
        "copilot_summary": copilot_summary,
        "sync_warnings": [warning.to_dict() for warning in sync_warnings],
        "has_any_source": has_calendar or has_clickup_tasks or clickup_live or has_copilot,
        "sources_used": _sources_list(calendar_summary, clickup_block, has_copilot),
    }


def _clickup_connected_pending(block: str) -> bool:
    return "connected" in block.lower() and "not connected" not in block.lower()


def has_clickup_connected_pending(clickup_block: str) -> bool:
    return _clickup_connected_pending(clickup_block)


def _sources_list(calendar_summary, clickup_block: str, has_copilot: bool) -> list[str]:
    sources: list[str] = []
    if calendar_summary is not None:
        sources.append("calendar")
    if _clickup_connected_pending(clickup_block):
        sources.append("clickup")
    if has_copilot:
        sources.append("copilot")
    return sources


def _estimate_clickup_load(task: dict, energy_score: int) -> int:
    """Map ClickUp priority + due urgency to cognitive load 1-10."""
    pri = (task.get("priority") or "normal").lower()
    due = (task.get("due_label") or "").lower()
    base = 5
    if pri == "urgent":
        base = 8
    elif pri == "high":
        base = 7
    elif pri == "low":
        base = 3
    if "overdue" in due:
        base = min(10, base + 1)
    elif "due today" in due:
        base = min(10, base + 1)
    # Scale slightly down if user is low energy — still store true load for routing
    return max(1, min(10, base))


def probe_calendar_health(refresh_token: str | None) -> SyncWarning | None:
    """Return a user-facing warning if calendar fetch fails, else None."""
    if not refresh_token:
        return None
    try:
        get_today_events(refresh_token)
        return None
    except CalendarSyncError as exc:
        logger.warning(
            "Calendar health probe failed code=%s: %s",
            exc.code.value,
            str(exc.cause or exc)[:200],
        )
        return calendar_warning_from_exception(exc)


def sync_user_clickup_tasks(db, user_id: str) -> tuple[int, list[SyncWarning]]:
    """
    Fetch the user's live ClickUp tasks and import any new ones into the Freeside
    task pool. Returns (inserted_count, warnings). Never raises.
    """
    warnings: list[SyncWarning] = []
    try:
        row = _load_clickup_row(db, user_id)
    except ClickUpSyncError as exc:
        warnings.append(clickup_warning_from_exception(exc))
        return 0, warnings
    api_token = get_api_token(user_id, db) if row else None
    if not row or not api_token:
        return 0, warnings
    if not row.get("external_team_id") and not row.get("workspace_name"):
        warnings.append(SyncWarning(
            SyncErrorCode.CLICKUP_NO_WORKSPACE,
            SYNC_ERROR_MESSAGES[SyncErrorCode.CLICKUP_NO_WORKSPACE],
            "clickup",
        ))
        return 0, warnings
    try:
        summary = fetch_clickup_summary(
            api_token,
            row.get("workspace_name"),
            team_id=row.get("external_team_id"),
        )
    except (ClickUpAuthError, ClickUpSyncError) as exc:
        logger.warning(
            "ClickUp task sync failed for user_id=%s code=%s: %s",
            user_id,
            exc.code.value,
            str(exc.cause or exc)[:200],
        )
        warnings.append(clickup_warning_from_exception(exc))
        return 0, warnings
    return sync_clickup_tasks_to_db(db, user_id, summary), warnings


def sync_clickup_tasks_to_db(db, user_id: str, clickup_summary: dict | None) -> int:
    """Import open ClickUp assigned tasks into Freeside pending pool (dedupe by title)."""
    if not clickup_summary or not clickup_summary.get("tasks"):
        return 0

    existing = (
        db.table("tasks")
        .select("title")
        .eq("user_id", user_id)
        .in_("status", ["pending", "active"])
        .execute()
    )
    existing_titles = {(r.get("title") or "").strip().lower() for r in (existing.data or [])}

    inserted = 0
    for task in clickup_summary["tasks"]:
        title = (task.get("name") or "").strip()
        if not title or title.lower() in existing_titles:
            continue
        load = _estimate_clickup_load(task, 5)
        try:
            db.table("tasks").insert({
                "user_id": user_id,
                "title": title[:200],
                "cognitive_load_score": load,
                "source": "clickup",
                "status": "pending",
            }).execute()
            existing_titles.add(title.lower())
            inserted += 1
        except Exception:
            continue
    return inserted


# In-memory focus list for CLCS boost (same process as plan-day)
_day_plan_focus: dict[str, list[str]] = {}


def set_day_plan_focus(user_id: str, titles: list[str]) -> None:
    _day_plan_focus[user_id] = [t.strip() for t in titles if t.strip()]


def get_day_plan_focus(user_id: str) -> list[str]:
    return _day_plan_focus.get(user_id, [])


def insert_suggested_tasks(db, user_id: str, suggestions: list[dict]) -> list[dict]:
    """Add Co-Pilot day-plan tasks to the pool."""
    existing = (
        db.table("tasks")
        .select("title")
        .eq("user_id", user_id)
        .in_("status", ["pending", "active"])
        .execute()
    )
    existing_titles = {(r.get("title") or "").strip().lower() for r in (existing.data or [])}

    inserted: list[dict] = []
    for t in suggestions:
        title = (t.get("title") or "").strip()
        if not title or title.lower() in existing_titles:
            continue
        load = max(1, min(10, int(t.get("cognitive_load_score") or 5)))
        try:
            row = db.table("tasks").insert({
                "user_id": user_id,
                "title": title[:200],
                "cognitive_load_score": load,
                "source": "copilot_suggested",
                "status": "pending",
            }).execute()
            if row.data:
                inserted.append(row.data[0])
                existing_titles.add(title.lower())
        except Exception:
            continue
    return inserted
