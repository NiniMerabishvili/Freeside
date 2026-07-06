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

    # Use a ±14h window around now rather than UTC midnight–midnight.
    # This captures "today" correctly for any timezone (GMT-12 to GMT+14)
    # without needing to know the user's local timezone.
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    start_of_day = (now - timedelta(hours=14)).isoformat()
    end_of_day   = (now + timedelta(hours=14)).isoformat()

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

    All-day events (holidays, travel, birthdays) are separated from timed
    meetings because they do NOT consume focused-work time. Only timed events
    contribute to meeting_count and total_meeting_minutes — the two signals
    the AI uses to estimate cognitive load.
    """
    timed_summaries: list[str] = []
    all_day_titles: list[str] = []
    back_to_back_count = 0
    total_meeting_minutes = 0
    prev_end_dt: datetime | None = None

    for event in events:
        title = event.get("summary", "Untitled event")
        start_info = event.get("start", {})
        end_info = event.get("end", {})

        # All-day event — 'date' key only, no 'dateTime'
        # These are holidays, birthdays, travel markers, OOO blocks etc.
        # They are NOT meetings and do NOT drain focused-work energy directly.
        if "dateTime" not in start_info:
            all_day_titles.append(title)
            prev_end_dt = None
            continue

        start_str = start_info.get("dateTime", "")
        end_str = end_info.get("dateTime", "")
        if not start_str or not end_str:
            continue

        start_dt = datetime.fromisoformat(start_str)
        end_dt = datetime.fromisoformat(end_str)
        duration = max(0, int((end_dt - start_dt).total_seconds() / 60))
        total_meeting_minutes += duration
        timed_summaries.append(f"- {title} ({duration} min)")

        if prev_end_dt is not None:
            if start_dt.tzinfo and prev_end_dt.tzinfo:
                gap = (start_dt - prev_end_dt).total_seconds() / 60
                if gap < 15:
                    back_to_back_count += 1

        prev_end_dt = end_dt

    # Build the event list shown to the AI
    event_lines: list[str] = []
    if timed_summaries:
        event_lines += timed_summaries
    if all_day_titles:
        # Show all-day items as low-weight context, not meetings
        joined = ", ".join(all_day_titles)
        event_lines.append(f"- All-day context (not meetings): {joined}")

    return {
        # Only count timed meetings — this is the cognitive load signal
        "event_count": len(timed_summaries),
        "all_day_event_count": len(all_day_titles),
        "total_meeting_minutes": total_meeting_minutes,
        "back_to_back_count": back_to_back_count,
        "event_list": "\n".join(event_lines) if event_lines else "No meetings today",
    }
