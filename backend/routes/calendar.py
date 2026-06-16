"""
Calendar routes — Google Calendar OAuth flow and event fetching.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
import os
from pathlib import Path
from supabase import create_client
from dotenv import load_dotenv

from services.calendar import get_today_events, summarize_events

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

router = APIRouter()

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
    state = user_id. Stores refresh token, then redirects back to onboarding step 5.
    """
    # User denied access
    if error:
        return RedirectResponse(f"{FRONTEND_URL}/onboarding?calendar=denied")

    try:
        flow = _create_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        if not credentials.refresh_token:
            # Token exchange succeeded but no refresh token — prompt re-consent
            return RedirectResponse(
                f"{FRONTEND_URL}/onboarding?calendar=no_refresh_token"
            )

        # Upsert so it works even if the profile row wasn't created by the trigger yet
        supabase.table("profiles").upsert(
            {
                "id": state,
                "google_refresh_token": credentials.refresh_token,
                "google_calendar_connected": True,
            }
        ).execute()

        # Return to onboarding — wizard will detect the param and jump to step 5
        return RedirectResponse(f"{FRONTEND_URL}/onboarding?calendar=connected")

    except Exception as e:
        print(f"Calendar OAuth error: {e}")
        return RedirectResponse(f"{FRONTEND_URL}/onboarding?calendar=error")


@router.get("/events/today")
def get_today_calendar_events(user_id: str):
    """
    Fetch and summarize today's calendar events for a user.
    Used by the dashboard energy widget.
    """
    profile = (
        supabase.table("profiles")
        .select("google_refresh_token, google_calendar_connected, peak_focus_time, work_style, daily_work_hours")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )

    if not profile or not profile.get("google_calendar_connected"):
        return {"connected": False, "events": [], "summary": None}

    try:
        events = get_today_events(profile["google_refresh_token"])
        summary = summarize_events(events)
        return {"connected": True, "events": events, "summary": summary}
    except Exception as e:
        print(f"Calendar fetch error for user {user_id}: {e}")
        return {"connected": True, "error": str(e), "events": [], "summary": None}


@router.delete("/disconnect")
def disconnect_calendar(user_id: str):
    """Remove Google Calendar connection for a user."""
    supabase.table("profiles").update(
        {
            "google_refresh_token": None,
            "google_calendar_connected": False,
        }
    ).eq("id", user_id).execute()
    return {"status": "disconnected"}
