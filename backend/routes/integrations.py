"""Integration routes — ClickUp OAuth, workspace selection, task preview."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from pathlib import Path
import os
from dotenv import load_dotenv
from supabase import create_client

from services.clickup import (
    fetch_clickup_summary,
    list_teams,
    verify_token,
)

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

router = APIRouter()

supabase = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3001")
CLICKUP_TOKEN_URL = "https://api.clickup.com/api/v2/oauth/token"


class ClickUpWorkspaceRequest(BaseModel):
    user_id: str
    team_id: str
    team_name: str


def _clickup_oauth_configured() -> bool:
    """True when CLICKUP_CLIENT_ID and CLICKUP_CLIENT_SECRET are set in backend/.env."""
    client_id = os.getenv("CLICKUP_CLIENT_ID", "")
    client_secret = os.getenv("CLICKUP_CLIENT_SECRET", "")
    return bool(
        client_id
        and client_secret
        and client_id not in ("your_clickup_client_id", "")
        and client_secret not in ("your_clickup_client_secret", "")
    )


def _redirect_uri() -> str:
    return f"{BACKEND_URL}/integrations/clickup/auth/callback"


def _frontend_redirect(path: str, query: str) -> RedirectResponse:
    sep = "&" if "?" in path else "?"
    return RedirectResponse(f"{FRONTEND_URL}{path}{sep}{query}")


def _load_clickup_row(user_id: str) -> dict | None:
    try:
        resp = (
            supabase.table("user_integrations")
            .select("*")
            .eq("user_id", user_id)
            .eq("integration_type", "clickup")
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.warning("user_integrations lookup failed: %s", str(exc)[:200])
        return None


@router.get("/status")
def integration_status(user_id: str):
    """Return connection status for supported integrations."""
    clickup = _load_clickup_row(user_id) or {}
    has_token = bool(clickup.get("is_connected") and clickup.get("api_token"))
    has_workspace = bool(clickup.get("external_team_id"))
    return {
        "clickup": {
            "connected": has_token and has_workspace,
            "authenticated": has_token,
            "needs_workspace": has_token and not has_workspace,
            "workspace_name": clickup.get("workspace_name"),
            "account_label": clickup.get("account_label"),
            "updated_at": clickup.get("updated_at"),
        },
    }


@router.get("/clickup/auth/url")
def get_clickup_auth_url(user_id: str, return_to: str = "settings"):
    """Generate ClickUp OAuth URL (same pattern as Google Calendar)."""
    if not _clickup_oauth_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "ClickUp OAuth is not configured. Add CLICKUP_CLIENT_ID and "
                "CLICKUP_CLIENT_SECRET to backend/.env (create an app in ClickUp Settings → Apps)."
            ),
        )

    client_id = os.getenv("CLICKUP_CLIENT_ID", "")
    redirect_uri = quote(_redirect_uri(), safe="")
    safe_return = "onboarding" if return_to == "onboarding" else "settings"
    state = quote(f"{user_id}|{safe_return}", safe="")
    auth_url = (
        f"https://app.clickup.com/api"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )
    return {"auth_url": auth_url}


@router.get("/clickup/auth/callback")
def clickup_auth_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Handle ClickUp OAuth callback; store token then send user to workspace picker."""
    return_to = "settings"
    if state and "|" in state:
        _, return_to = state.split("|", 1)

    base_path = "/onboarding" if return_to == "onboarding" else "/settings"

    if error or not code or not state:
        return _frontend_redirect(base_path, f"clickup=denied")

    user_id = state.split("|", 1)[0]

    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(
                CLICKUP_TOKEN_URL,
                json={
                    "client_id": os.getenv("CLICKUP_CLIENT_ID"),
                    "client_secret": os.getenv("CLICKUP_CLIENT_SECRET"),
                    "code": code,
                },
            )
            resp.raise_for_status()
            access_token = resp.json().get("access_token")

        if not access_token:
            return _frontend_redirect(base_path, "clickup=error")

        user = verify_token(access_token)
        account_label = user.get("email") or user.get("username") or "ClickUp user"
        now = datetime.now(timezone.utc).isoformat()

        supabase.table("user_integrations").upsert(
            {
                "user_id": user_id,
                "integration_type": "clickup",
                "is_connected": True,
                "api_token": access_token,
                "account_label": account_label,
                "workspace_name": None,
                "external_team_id": None,
                "updated_at": now,
            },
            on_conflict="user_id,integration_type",
        ).execute()

        return _frontend_redirect(base_path, "clickup=select_workspace")

    except Exception as exc:
        logger.warning("ClickUp OAuth callback failed: %s", str(exc)[:200])
        return _frontend_redirect(base_path, "clickup=error")


@router.get("/clickup/workspaces")
def clickup_workspaces(user_id: str):
    """List authorized ClickUp workspaces after OAuth."""
    row = _load_clickup_row(user_id)
    if not row or not row.get("api_token"):
        raise HTTPException(status_code=404, detail="ClickUp not connected. Sign in first.")

    try:
        teams = list_teams(row["api_token"])
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise HTTPException(status_code=400, detail="ClickUp session expired. Connect again.") from exc
        raise HTTPException(status_code=502, detail="Could not reach ClickUp API.") from exc

    return {
        "account_label": row.get("account_label"),
        "workspaces": [
            {"id": str(t.get("id")), "name": t.get("name") or "Workspace"}
            for t in teams
        ],
    }


@router.post("/clickup/workspace")
def select_clickup_workspace(request: ClickUpWorkspaceRequest):
    """Save the workspace the user chose after OAuth."""
    row = _load_clickup_row(request.user_id)
    if not row or not row.get("api_token"):
        raise HTTPException(status_code=404, detail="ClickUp not connected. Sign in first.")

    team_id = request.team_id.strip()
    team_name = request.team_name.strip()
    if not team_id or not team_name:
        raise HTTPException(status_code=400, detail="Workspace is required.")

    try:
        summary = fetch_clickup_summary(
            row["api_token"],
            team_name,
            team_id=team_id,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise HTTPException(status_code=400, detail="ClickUp session expired. Connect again.") from exc
        raise HTTPException(status_code=502, detail="Could not reach ClickUp API.") from exc

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("user_integrations").upsert(
        {
            "user_id": request.user_id,
            "integration_type": "clickup",
            "is_connected": True,
            "api_token": row["api_token"],
            "account_label": row.get("account_label"),
            "workspace_name": team_name,
            "external_team_id": team_id,
            "updated_at": now,
        },
        on_conflict="user_id,integration_type",
    ).execute()

    return {
        "status": "connected",
        "workspace": team_name,
        "account_label": row.get("account_label"),
        "task_count": summary.get("task_count", 0),
        "preview": summary.get("task_list", ""),
    }


@router.delete("/clickup/disconnect")
def disconnect_clickup(user_id: str):
    supabase.table("user_integrations").upsert(
        {
            "user_id": user_id,
            "integration_type": "clickup",
            "is_connected": False,
            "api_token": None,
            "workspace_name": None,
            "external_team_id": None,
            "account_label": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id,integration_type",
    ).execute()
    return {"status": "disconnected"}


@router.get("/clickup/tasks")
def clickup_tasks_preview(user_id: str):
    """Live task fetch for Settings preview."""
    row = _load_clickup_row(user_id)
    if not row or not row.get("api_token"):
        raise HTTPException(status_code=404, detail="ClickUp not connected.")

    if not row.get("external_team_id"):
        raise HTTPException(status_code=400, detail="Select a ClickUp workspace first.")

    try:
        summary = fetch_clickup_summary(
            row["api_token"],
            row.get("workspace_name"),
            team_id=row.get("external_team_id"),
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise HTTPException(status_code=400, detail="ClickUp session expired. Connect again.") from exc
        raise HTTPException(status_code=502, detail="ClickUp API error.") from exc

    return summary
