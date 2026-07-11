"""Google Calendar service - fetches and summarizes today's events."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from services.integration_errors import (
    CalendarSyncError,
    SYNC_ERROR_MESSAGES,
    SyncErrorCode,
)

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)


def get_today_events(refresh_token: str) -> list:
    """
    Fetch today's Google Calendar events using a stored refresh token.
    Raises CalendarSyncError if the token is revoked or the API fetch fails.
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
    except RefreshError as exc:
        logger.info("Google Calendar refresh token rejected: %s", str(exc)[:200])
        raise CalendarSyncError(
            SyncErrorCode.CALENDAR_AUTH_REVOKED,
            SYNC_ERROR_MESSAGES[SyncErrorCode.CALENDAR_AUTH_REVOKED],
            cause=exc,
        ) from exc

    service = build("calendar", "v3", credentials=creds)

    # Use a +/-14h window around now rather than UTC midnight-to-midnight.
    now = datetime.now(timezone.utc)
    start_of_day = (now - timedelta(hours=14)).isoformat()
    end_of_day = (now + timedelta(hours=14)).isoformat()

    try:
        events_result = (
            service.events()  # type: ignore[attr-defined]
            .list(
                calendarId="primary",
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except HttpError as exc:
        status = getattr(getattr(exc, "resp", None), "status", None)
        code = (
            SyncErrorCode.CALENDAR_AUTH_REVOKED
            if status in (401, 403)
            else SyncErrorCode.CALENDAR_FETCH_FAILED
        )
        logger.warning(
            "Google Calendar API error status=%s: %s",
            status,
            str(exc)[:200],
        )
        raise CalendarSyncError(code, SYNC_ERROR_MESSAGES[code], cause=exc) from exc
    except (TimeoutError, OSError) as exc:
        logger.warning("Google Calendar network error: %s", str(exc)[:200])
        raise CalendarSyncError(
            SyncErrorCode.CALENDAR_FETCH_FAILED,
            SYNC_ERROR_MESSAGES[SyncErrorCode.CALENDAR_FETCH_FAILED],
            cause=exc,
        ) from exc

    return events_result.get("items", [])


def summarize_events(events: list) -> dict:
    """
    Turn raw Google Calendar events into structured signals for the AI.

    All-day events are separated from timed meetings because they do not consume
    focused-work time.
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

        if prev_end_dt is not None and start_dt.tzinfo and prev_end_dt.tzinfo:
            gap = (start_dt - prev_end_dt).total_seconds() / 60
            if gap < 15:
                back_to_back_count += 1

        prev_end_dt = end_dt

    event_lines: list[str] = []
    if timed_summaries:
        event_lines += timed_summaries
    if all_day_titles:
        joined = ", ".join(all_day_titles)
        event_lines.append(f"- All-day context (not meetings): {joined}")

    return {
        "event_count": len(timed_summaries),
        "all_day_event_count": len(all_day_titles),
        "total_meeting_minutes": total_meeting_minutes,
        "back_to_back_count": back_to_back_count,
        "event_list": "\n".join(event_lines) if event_lines else "No meetings today",
    }
