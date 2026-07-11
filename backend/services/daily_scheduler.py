"""Daily task generation — energy, time blocks, and calendar-aware scheduling."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any

from supabase import Client

from services.calendar import get_today_events, summarize_events
from services.integration_errors import CalendarSyncError
from services.router import route_tasks
from services.token_vault import get_google_refresh_token
from services.time_blocks import compute_free_blocks, summarize_free_time

logger = logging.getLogger(__name__)


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    try:
        parts = str(value).split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


def compute_daily_cognitive_budget(
    effective_capacity: int,
    free_minutes: int,
    meeting_minutes: int,
    daily_work_hours: int,
) -> dict:
    """
    Max cognitive load points assignable today without exceeding capacity.

    Scales effective CLCS capacity by available focus time vs a full work day.
    """
    daily_work_hours = max(4, min(12, daily_work_hours or 8))
    nominal_minutes = daily_work_hours * 60
    usable = max(0, free_minutes)
    time_ratio = min(1.0, usable / nominal_minutes) if nominal_minutes else 0.5

    # Meeting density further reduces assignable deep-work load
    meeting_penalty = min(0.35, (meeting_minutes / 60.0) * 0.08)
    load_factor = max(0.25, time_ratio - meeting_penalty)

    max_load_points = round(effective_capacity * load_factor * 2.5, 1)
    max_minutes = usable

    return {
        "effective_capacity": effective_capacity,
        "max_load_points": max_load_points,
        "max_focus_minutes": max_minutes,
        "time_ratio": round(time_ratio, 2),
        "meeting_minutes": meeting_minutes,
    }


def _task_load_cost(task: dict) -> float:
    load = int(task.get("cognitive_load_score") or 5)
    minutes = int(task.get("estimated_minutes") or 30)
    return load * (minutes / 45.0)


def _fits_block(task: dict, block: dict) -> bool:
    needed = int(task.get("estimated_minutes") or 30)
    return block.get("minutes", 0) >= needed - 5


def _assign_block(task: dict, block: dict) -> dict:
    """Slice a time block for a task; returns assignment metadata."""
    needed = int(task.get("estimated_minutes") or 30)
    start_dt = datetime.fromisoformat(block["start"])
    end_dt = start_dt + timedelta(minutes=needed)
    remaining = block["minutes"] - needed
    block["start"] = end_dt.isoformat()
    block["minutes"] = max(0, remaining)
    return {
        "scheduled_block_start": start_dt.strftime("%H:%M:%S"),
        "scheduled_block_end": end_dt.strftime("%H:%M:%S"),
    }


def select_tasks_for_today(
    candidate_tasks: list[dict],
    budget: dict,
    free_blocks: list[dict],
    effective_capacity: int,
) -> tuple[list[dict], list[dict]]:
    """
    Greedy pack: pick tasks that fit cognitive budget and time blocks.
    Returns (selected, deferred).
    """
    if not candidate_tasks:
        return [], []

    blocks = [{**b} for b in free_blocks]
    max_points = budget["max_load_points"]
    max_minutes = budget["max_focus_minutes"]

    ordered = sorted(
        candidate_tasks,
        key=lambda t: (
            t.get("milestone_order") or 999,
            t.get("step_order") or 999,
            -int(t.get("cognitive_load_score") or 5),
        ),
    )

    selected: list[dict] = []
    deferred: list[dict] = []
    used_points = 0.0
    used_minutes = 0

    for task in ordered:
        load_cost = _task_load_cost(task)
        minutes = int(task.get("estimated_minutes") or 30)
        load = int(task.get("cognitive_load_score") or 5)

        if load - effective_capacity > 2:
            deferred.append({**task, "defer_reason": "energy_mismatch"})
            continue
        if used_points + load_cost > max_points:
            deferred.append({**task, "defer_reason": "capacity_exceeded"})
            continue
        if used_minutes + minutes > max_minutes:
            deferred.append({**task, "defer_reason": "no_time_remaining"})
            continue

        block_idx = next((i for i, b in enumerate(blocks) if _fits_block(task, b)), None)
        if block_idx is None:
            deferred.append({**task, "defer_reason": "no_free_block"})
            continue

        assignment = _assign_block(task, blocks[block_idx])
        selected.append({**task, **assignment})
        used_points += load_cost
        used_minutes += minutes

    return selected, deferred


def fetch_milestone_candidates(db: Client, user_id: str, today: date) -> list[dict]:
    """Pending tasks from milestones due on or before today."""
    today_str = today.isoformat()
    try:
        ms_resp = (
            db.table("milestones")
            .select("id, title, goal_id, milestone_order, scheduled_date, status")
            .eq("user_id", user_id)
            .in_("status", ["pending", "active"])
            .lte("scheduled_date", today_str)
            .execute()
        )
        milestones = ms_resp.data or []
    except Exception:
        milestones = []

    if not milestones:
        # Legacy: milestone-as-task rows without milestone entity
        try:
            legacy = (
                db.table("tasks")
                .select("*")
                .eq("user_id", user_id)
                .eq("is_milestone", True)
                .eq("status", "pending")
                .lte("scheduled_date", today_str)
                .execute()
            )
            return [{
                **t,
                "milestone_title": t.get("title"),
                "milestone_order": t.get("milestone_order"),
            } for t in (legacy.data or [])]
        except Exception:
            return []

    ms_ids = [m["id"] for m in milestones]
    ms_meta = {m["id"]: m for m in milestones}

    tasks_resp = (
        db.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .in_("milestone_id", ms_ids)
        .eq("status", "pending")
        .execute()
    )
    candidates = []
    for t in tasks_resp.data or []:
        mid = t.get("milestone_id")
        meta = ms_meta.get(mid, {})
        candidates.append({
            **t,
            "milestone_title": meta.get("title"),
            "milestone_order": meta.get("milestone_order"),
            "goal_id": t.get("goal_id") or meta.get("goal_id"),
        })
    return candidates


def persist_daily_assignments(
    db: Client,
    user_id: str,
    today: date,
    selected: list[dict],
) -> None:
    """Write daily_assigned_date and time blocks for scheduled tasks."""
    today_str = today.isoformat()
    for task in selected:
        updates: dict[str, Any] = {"daily_assigned_date": today_str}
        if task.get("scheduled_block_start"):
            updates["scheduled_block_start"] = task["scheduled_block_start"]
        if task.get("scheduled_block_end"):
            updates["scheduled_block_end"] = task["scheduled_block_end"]
        try:
            db.table("tasks").update(updates).eq("id", task["id"]).eq("user_id", user_id).execute()
        except Exception:
            try:
                db.table("tasks").update({"daily_assigned_date": today_str}).eq(
                    "id", task["id"]
                ).eq("user_id", user_id).execute()
            except Exception:
                pass


def generate_daily_schedule(
    db: Client,
    user_id: str,
    profile: dict,
    energy_score: int,
    peak_focus_time: str | None = None,
) -> dict:
    """
    Auto-schedule milestone tasks for today using energy, free blocks, and calendar.

    Returns schedule metadata + selected/deferred task ids.
    """
    today = date.today()
    preview = route_tasks([], energy_score, peak_focus_time)
    effective_capacity = preview["effective_capacity"]

    events: list = []
    meeting_minutes = 0
    refresh_token = (
        get_google_refresh_token(user_id, db)
        if profile.get("google_calendar_connected")
        else None
    )
    if refresh_token:
        try:
            events = get_today_events(refresh_token)
            meeting_minutes = summarize_events(events).get("total_meeting_minutes", 0)
        except CalendarSyncError as exc:
            logger.warning(
                "Calendar unavailable for daily schedule user_id=%s code=%s: %s",
                user_id,
                exc.code.value,
                str(exc.cause or exc)[:200],
            )
            events = []

    free_blocks = compute_free_blocks(events, profile)
    free_summary = summarize_free_time(free_blocks)
    daily_work_hours = int(profile.get("daily_work_hours") or 8)

    budget = compute_daily_cognitive_budget(
        effective_capacity,
        free_summary["total_free_minutes"],
        meeting_minutes,
        daily_work_hours,
    )

    candidates = fetch_milestone_candidates(db, user_id, today)
    selected, deferred = select_tasks_for_today(
        candidates, budget, free_blocks, effective_capacity
    )

    if selected:
        persist_daily_assignments(db, user_id, today, selected)

    selected_ids = {t["id"] for t in selected}
    return {
        "date": today.isoformat(),
        "budget": budget,
        "free_time": free_summary,
        "selected_task_ids": list(selected_ids),
        "deferred_task_ids": [t["id"] for t in deferred],
        "deferred_tasks": deferred,
        "selected_count": len(selected),
        "deferred_count": len(deferred),
    }


def milestone_task_is_routable_today(task: dict, today: date | None = None) -> bool:
    """Milestone child tasks only surface when daily-assigned for today."""
    today = today or date.today()
    if not task.get("milestone_id"):
        return True
    assigned = task.get("daily_assigned_date")
    if not assigned:
        return False
    return str(assigned)[:10] == today.isoformat()


def build_milestone_groups(
    db: Client,
    routed_tasks: list[dict],
    deferred_milestone_tasks: list[dict] | None = None,
) -> list[dict]:
    """Group routed tasks under their milestone containers for the UI."""
    by_milestone: dict[str, dict] = {}
    all_tasks = list(routed_tasks) + list(deferred_milestone_tasks or [])

    for task in all_tasks:
        mid = task.get("milestone_id")
        if not mid:
            continue
        if mid not in by_milestone:
            by_milestone[mid] = {
                "milestone_id": mid,
                "milestone_title": task.get("milestone_title") or "Milestone",
                "goal_id": task.get("goal_id"),
                "progress_percent": 0,
                "active": [],
                "blocked": [],
                "deferred": [],
            }
        entry = by_milestone[mid]
        if task.get("milestone_title"):
            entry["milestone_title"] = task["milestone_title"]
        if task.get("visible") is False or task.get("defer_reason"):
            if task.get("defer_reason"):
                entry["deferred"].append(task)
            else:
                entry["blocked"].append(task)
        else:
            entry["active"].append(task)

    for mid, group in by_milestone.items():
        try:
            children = (
                db.table("tasks")
                .select("status")
                .eq("milestone_id", mid)
                .execute()
            ).data or []
            if children:
                done = sum(1 for c in children if c.get("status") == "completed")
                group["progress_percent"] = round(done / len(children) * 100)
        except Exception:
            pass
        group["active"].sort(key=lambda t: (t.get("step_order") or 99))
        group["blocked"].sort(key=lambda t: (t.get("step_order") or 99))
        group["deferred"].sort(key=lambda t: (t.get("step_order") or 99))

    return list(by_milestone.values())
