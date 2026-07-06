"""Calendar free-block computation for daily task scheduling."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone


def _parse_event_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def timed_events_to_busy_intervals(events: list) -> list[tuple[datetime, datetime]]:
    """Convert Google Calendar timed events into (start, end) intervals."""
    intervals: list[tuple[datetime, datetime]] = []
    for event in events:
        start_info = event.get("start", {})
        if "dateTime" not in start_info:
            continue
        start_dt = _parse_event_dt(start_info.get("dateTime", ""))
        end_dt = _parse_event_dt(event.get("end", {}).get("dateTime", ""))
        if start_dt and end_dt and end_dt > start_dt:
            intervals.append((start_dt, end_dt))
    intervals.sort(key=lambda x: x[0])
    return intervals


def _default_work_window(profile: dict | None) -> tuple[time, time]:
    """Work day bounds from profile peak focus + daily_work_hours."""
    profile = profile or {}
    hours = int(profile.get("daily_work_hours") or 8)
    hours = max(4, min(12, hours))
    peak = (profile.get("peak_focus_time") or "morning").lower()
    if peak in ("early_bird", "morning"):
        start = time(8, 0)
    elif peak == "afternoon":
        start = time(10, 0)
    elif peak in ("evening", "night"):
        start = time(13, 0)
    else:
        start = time(9, 0)
    end_hour = min(22, start.hour + hours)
    end_minute = start.minute
    return start, time(end_hour, end_minute)


def _today_bounds(work_start: time, work_end: time) -> tuple[datetime, datetime]:
    now = datetime.now().astimezone()
    day_start = now.replace(
        hour=work_start.hour, minute=work_start.minute, second=0, microsecond=0
    )
    day_end = now.replace(
        hour=work_end.hour, minute=work_end.minute, second=0, microsecond=0
    )
    if day_end <= day_start:
        day_end += timedelta(hours=8)
    return day_start, day_end


def compute_free_blocks(
    events: list,
    profile: dict | None,
    *,
    min_block_minutes: int = 20,
) -> list[dict]:
    """
    Find available focus blocks today, avoiding calendar meetings.

    Returns: [{ start: ISO, end: ISO, minutes: int }, ...]
    """
    work_start, work_end = _default_work_window(profile)
    day_start, day_end = _today_bounds(work_start, work_end)
    now = datetime.now().astimezone()

    busy = timed_events_to_busy_intervals(events)
    cursor = max(now, day_start)
    free: list[dict] = []

    for b_start, b_end in busy:
        if b_end <= cursor:
            continue
        if b_start > cursor:
            gap_min = int((b_start - cursor).total_seconds() / 60)
            if gap_min >= min_block_minutes:
                free.append({
                    "start": cursor.isoformat(),
                    "end": b_start.isoformat(),
                    "minutes": gap_min,
                })
        cursor = max(cursor, b_end)

    if cursor < day_end:
        gap_min = int((day_end - cursor).total_seconds() / 60)
        if gap_min >= min_block_minutes:
            free.append({
                "start": cursor.isoformat(),
                "end": day_end.isoformat(),
                "minutes": gap_min,
            })

    if not free and not busy:
        total = int((day_end - max(now, day_start)).total_seconds() / 60)
        if total >= min_block_minutes:
            free.append({
                "start": max(now, day_start).isoformat(),
                "end": day_end.isoformat(),
                "minutes": total,
            })

    return free


def summarize_free_time(free_blocks: list[dict]) -> dict:
    total = sum(b.get("minutes", 0) for b in free_blocks)
    return {
        "block_count": len(free_blocks),
        "total_free_minutes": total,
        "blocks": free_blocks,
    }
