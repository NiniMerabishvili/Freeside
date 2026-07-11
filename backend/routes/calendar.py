"""Calendar routes - Google Calendar OAuth flow and event fetching."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from supabase import create_client

from services.calendar import get_today_events, summarize_events
from services.integration_errors import CalendarSyncError, SyncErrorCode
from services.token_vault import get_google_refresh_token, set_google_refresh_token

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

router = APIRouter()
logger = logging.getLogger(__name__)

supabase = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3001")


def _create_flow() -> Flow:
    """Create a Google OAuth flow instance."""
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "redirect_uris": [f"{BACKEND_URL}/calendar/auth/callback"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = f"{BACKEND_URL}/calendar/auth/callback"
    return flow


@router.get("/auth/url")
def get_google_auth_url(user_id: str):
    """Generate Google OAuth URL for calendar access."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or client_id == "your_google_client_id":
        raise HTTPException(
            status_code=503,
            detail="Google Calendar integration is not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to your .env file.",
        )
    if not client_secret or client_secret == "your_google_client_secret":
        raise HTTPException(
            status_code=503,
            detail="Google Calendar integration is not configured. Add GOOGLE_CLIENT_SECRET to your .env file.",
        )

    flow = _create_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        state=user_id,
        prompt="consent",
        include_granted_scopes="true",
    )
    return {"auth_url": auth_url}


@router.get("/auth/callback")
def google_auth_callback(code: str, state: str, error: str = None):
    """
    Handle Google OAuth callback.
    state = user_id. Stores refresh token, then redirects back to onboarding.
    """
    if error:
        return RedirectResponse(f"{FRONTEND_URL}/onboarding?calendar=denied")

    try:
        flow = _create_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        if not credentials.refresh_token:
            return RedirectResponse(
                f"{FRONTEND_URL}/onboarding?calendar=no_refresh_token"
            )

        supabase.table("profiles").upsert({"id": state}).execute()
        set_google_refresh_token(state, credentials.refresh_token, supabase)
        supabase.table("profiles").update(
            {"google_calendar_connected": True}
        ).eq("id", state).execute()

        profile = (
            supabase.table("profiles")
            .select("onboarding_completed")
            .eq("id", state)
            .single()
            .execute()
            .data
        )
        if profile and profile.get("onboarding_completed"):
            return RedirectResponse(f"{FRONTEND_URL}/dashboard?calendar=connected")

        return RedirectResponse(f"{FRONTEND_URL}/onboarding?calendar=connected")

    except Exception as exc:
        logger.warning("Calendar OAuth error for user_id=%s: %s", state, str(exc)[:200])
        return RedirectResponse(f"{FRONTEND_URL}/onboarding?calendar=error")


@router.get("/events/today")
def get_today_calendar_events(user_id: str):
    """
    Fetch and summarize today's calendar events for a user.
    Used by the dashboard energy widget.
    """
    profile = (
        supabase.table("profiles")
        .select("google_calendar_connected, peak_focus_time, work_style, daily_work_hours")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )

    if not profile or not profile.get("google_calendar_connected"):
        return {"connected": False, "events": [], "summary": None}

    try:
        refresh_token = get_google_refresh_token(user_id, supabase)
        if not refresh_token:
            return {"connected": False, "events": [], "summary": None}
        events = get_today_events(refresh_token)
        summary = summarize_events(events)
        return {"connected": True, "events": events, "summary": summary}
    except CalendarSyncError as exc:
        logger.warning(
            "Calendar fetch failed for user_id=%s code=%s: %s",
            user_id,
            exc.code.value,
            str(exc.cause or exc)[:200],
        )
        status_code = 401 if exc.code == SyncErrorCode.CALENDAR_AUTH_REVOKED else 503
        raise HTTPException(status_code=status_code, detail=exc.message) from exc


@router.delete("/disconnect")
def disconnect_calendar(user_id: str):
    """Remove Google Calendar connection for a user."""
    set_google_refresh_token(user_id, None, supabase)
    supabase.table("profiles").update(
        {"google_calendar_connected": False}
    ).eq("id", user_id).execute()
    return {"status": "disconnected"}
