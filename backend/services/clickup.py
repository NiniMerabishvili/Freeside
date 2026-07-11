"""ClickUp API client — OAuth + assigned tasks for AI day planning."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import httpx

from services.integration_errors import (
    ClickUpAuthError,
    ClickUpSyncError,
    SYNC_ERROR_MESSAGES,
    SyncErrorCode,
)
from services.token_vault import get_api_token

logger = logging.getLogger(__name__)

CLICKUP_API = "https://api.clickup.com/api/v2"
PRIORITY_LABEL = {1: "urgent", 2: "high", 3: "normal", 4: "low", None: "none"}


def _clickup_error(exc: Exception, operation: str) -> ClickUpAuthError | ClickUpSyncError:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            logger.warning("ClickUp auth failed during %s: status=%s", operation, status)
            return ClickUpAuthError(cause=exc)
        logger.warning("ClickUp API failed during %s: status=%s", operation, status)
        return ClickUpSyncError(cause=exc)
    logger.warning("ClickUp request failed during %s: %s", operation, str(exc)[:200])
    return ClickUpSyncError(cause=exc)


def auth_header(api_token: str) -> str:
    """Personal tokens use raw pk_…; OAuth tokens use Bearer."""
    token = api_token.strip()
    if token.startswith("pk_"):
        return token
    return f"Bearer {token}"


def _headers(api_token: str) -> dict[str, str]:
    return {"Authorization": auth_header(api_token), "Content-Type": "application/json"}


def verify_token(api_token: str) -> dict[str, Any]:
    """Validate token and return ClickUp user profile."""
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(f"{CLICKUP_API}/user", headers=_headers(api_token))
            resp.raise_for_status()
            return resp.json().get("user", {})
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as exc:
        raise _clickup_error(exc, "verify_token") from exc


def list_teams(api_token: str) -> list[dict]:
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(f"{CLICKUP_API}/team", headers=_headers(api_token))
            resp.raise_for_status()
            return resp.json().get("teams", [])
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as exc:
        raise _clickup_error(exc, "list_teams") from exc


def _pick_team(teams: list[dict], workspace_name: str | None, team_id: str | None = None) -> dict | None:
    if not teams:
        return None
    if team_id:
        for team in teams:
            if str(team.get("id")) == str(team_id):
                return team
    if workspace_name:
        needle = workspace_name.strip().lower()
        for team in teams:
            if needle in (team.get("name") or "").lower():
                return team
    return teams[0]


def fetch_assigned_tasks(
    api_token: str,
    clickup_user_id: int,
    team_id: str,
    *,
    limit: int = 30,
) -> list[dict]:
    """Open tasks assigned to the user in a workspace."""
    params: dict[str, Any] = {
        "assignees[]": clickup_user_id,
        "include_closed": "false",
        "subtasks": "true",
        "order_by": "due_date",
        "reverse": "false",
    }
    try:
        with httpx.Client(timeout=25) as client:
            resp = client.get(
                f"{CLICKUP_API}/team/{team_id}/task",
                headers=_headers(api_token),
                params=params,
            )
            resp.raise_for_status()
            tasks = resp.json().get("tasks", [])
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as exc:
        raise _clickup_error(exc, "fetch_assigned_tasks") from exc
    return tasks[:limit]


def _due_label(due_ms: str | int | None) -> str:
    if not due_ms:
        return "no due date"
    try:
        ms = int(due_ms)
        due = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()
    except (TypeError, ValueError):
        return "no due date"
    today = date.today()
    if due < today:
        return f"overdue ({due.isoformat()})"
    if due == today:
        return "due today"
    return f"due {due.isoformat()}"


def summarize_tasks(tasks: list[dict]) -> dict[str, Any]:
    """Build AI-friendly summary from ClickUp task payloads."""
    if not tasks:
        return {
            "task_count": 0,
            "due_today_count": 0,
            "overdue_count": 0,
            "high_priority_count": 0,
            "task_list": "No open assigned tasks in ClickUp.",
            "tasks": [],
        }

    lines: list[str] = []
    due_today = overdue = high_pri = 0
    parsed: list[dict] = []

    for t in tasks:
        name = (t.get("name") or "Untitled").strip()
        status = (t.get("status") or {}).get("status") or "open"
        priority = t.get("priority")
        pri_id = priority.get("id") if isinstance(priority, dict) else priority
        pri_label = PRIORITY_LABEL.get(pri_id, "normal")
        due = _due_label(t.get("due_date"))
        if "due today" in due:
            due_today += 1
        if "overdue" in due:
            overdue += 1
        if pri_id in (1, 2):
            high_pri += 1
        url = t.get("url") or ""
        line = f"- {name} | {status} | priority: {pri_label} | {due}"
        if url:
            line += f" | {url}"
        lines.append(line)
        parsed.append({
            "name": name,
            "status": status,
            "priority": pri_label,
            "due_label": due,
            "url": url,
        })

    return {
        "task_count": len(tasks),
        "due_today_count": due_today,
        "overdue_count": overdue,
        "high_priority_count": high_pri,
        "task_list": "\n".join(lines),
        "tasks": parsed,
    }


def fetch_clickup_summary(
    api_token: str,
    workspace_name: str | None = None,
    *,
    team_id: str | None = None,
) -> dict[str, Any]:
    """
    Full pipeline: verify user → pick team → fetch tasks → summarize.
    Raises httpx.HTTPStatusError on auth/API failure.
    """
    user = verify_token(api_token)
    try:
        clickup_user_id = int(user["id"])
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("ClickUp user profile missing id during summary fetch")
        raise ClickUpSyncError(cause=exc) from exc
    teams = list_teams(api_token)
    team = _pick_team(teams, workspace_name, team_id)
    if not team:
        return {
            "connected": True,
            "user": user.get("username") or user.get("email"),
            "workspace": workspace_name or "",
            "task_count": 0,
            "due_today_count": 0,
            "overdue_count": 0,
            "high_priority_count": 0,
            "task_list": "No ClickUp workspace found for this account.",
            "tasks": [],
        }

    resolved_team_id = str(team["id"])
    team_name = team.get("name") or ""
    tasks = fetch_assigned_tasks(api_token, clickup_user_id, resolved_team_id)
    summary = summarize_tasks(tasks)
    return {
        "connected": True,
        "user": user.get("username") or user.get("email"),
        "workspace": team_name,
        "team_id": resolved_team_id,
        **summary,
    }


def format_clickup_block(summary: dict[str, Any]) -> str:
    """Plain-text block injected into Co-Pilot system context."""
    if not summary.get("connected"):
        return "ClickUp not connected."
    if not summary.get("workspace"):
        return "ClickUp account connected — no workspace selected yet."
    if summary.get("task_count", 0) == 0:
        ws = summary.get("workspace") or "workspace"
        return f"ClickUp connected ({ws}) — no open assigned tasks right now."

    return f"""- Workspace: {summary.get('workspace', 'unknown')}
- Open assigned tasks: {summary.get('task_count', 0)}
- Due today: {summary.get('due_today_count', 0)} | Overdue: {summary.get('overdue_count', 0)} | High/urgent: {summary.get('high_priority_count', 0)}
- Task list:
{summary.get('task_list', '')}"""


def get_clickup_context_from_db(db, user_id: str) -> str:
    """Load integration row and fetch live ClickUp summary for AI context."""
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
    except Exception as exc:
        logger.warning(
            "ClickUp integration lookup failed for user_id=%s: %s",
            user_id,
            str(exc)[:200],
        )
        raise ClickUpSyncError(
            SyncErrorCode.CLICKUP_FETCH_FAILED,
            SYNC_ERROR_MESSAGES[SyncErrorCode.CLICKUP_FETCH_FAILED],
            cause=exc,
        ) from exc

    api_token = get_api_token(user_id, db) if rows else None
    if not rows or not api_token:
        return "ClickUp not connected."

    row = rows[0]
    if not row.get("external_team_id") and not row.get("workspace_name"):
        label = row.get("account_label") or "ClickUp"
        return f"{label} connected — workspace not selected yet."

    try:
        summary = fetch_clickup_summary(
            api_token,
            row.get("workspace_name"),
            team_id=row.get("external_team_id"),
        )
        return format_clickup_block(summary)
    except (ClickUpAuthError, ClickUpSyncError):
        raise
