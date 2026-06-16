"""
Google Calendar service — Fetches and summarizes today's events.
"""
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from datetime import datetime, timezone
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)


def get_today_events(refresh_token: str) -> list:
    """
    Fetch today's Google Calendar events using a stored refresh token.
    Raises ValueError if the token is revoked or expired beyond repair.
    """
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    )

    try:
        creds.refresh(Request())
    except RefreshError as e:
        raise ValueError(
            f"Google Calendar token is revoked or expired. User must reconnect. ({e})"
        )

    service = build("calendar", "v3", credentials=creds)

    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

    try:
        events_result = (
            service.events()  # type: ignore
            .list(
                calendarId="primary",
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except Exception as e:
        raise RuntimeError(f"Google Calendar API error: {e}")

    return events_result.get("items", [])


def summarize_events(events: list) -> dict:
    """
    Turn raw Google Calendar events into structured signals for the AI.
    Handles both timed events (dateTime) and all-day events (date).
    """
    summaries = []
    back_to_back_count = 0
    total_meeting_minutes = 0
    prev_end_dt: datetime | None = None

    for event in events:
        title = event.get("summary", "Untitled event")
        start_info = event.get("start", {})
        end_info = event.get("end", {})

        # All-day event — has 'date' but no 'dateTime'
        if "date" in start_info and "dateTime" not in start_info:
            summaries.append(f"- {title} (all day)")
            prev_end_dt = None  # can't track gaps for all-day events
            continue

        start_str = start_info.get("dateTime", "")
        end_str = end_info.get("dateTime", "")

        if not start_str or not end_str:
            continue

        start_dt = datetime.fromisoformat(start_str)
        end_dt = datetime.fromisoformat(end_str)
        duration = max(0, int((end_dt - start_dt).total_seconds() / 60))
        total_meeting_minutes += duration
        summaries.append(f"- {title} ({duration} min)")

        # Check back-to-back (< 15 min gap from previous timed event)
        if prev_end_dt is not None:
            # Normalize timezone for comparison
            if start_dt.tzinfo and prev_end_dt.tzinfo:
                gap = (start_dt - prev_end_dt).total_seconds() / 60
            else:
                gap = 999  # can't compare, skip
            if gap < 15:
                back_to_back_count += 1

        prev_end_dt = end_dt

    return {
        "event_count": len(events),
        "total_meeting_minutes": total_meeting_minutes,
        "back_to_back_count": back_to_back_count,
        "event_list": "\n".join(summaries) if summaries else "No events today",
    }
