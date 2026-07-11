"""Multi-day goal planning — milestones entity + child tasks + energy forecasting."""
from __future__ import annotations

import logging
import math
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from supabase import Client

from services.ai import decompose_milestone_tasks
from services.calendar import get_today_events, summarize_events
from services.embeddings import embed_text
from services.integration_errors import CalendarSyncError
from services.token_vault import get_google_refresh_token

logger = logging.getLogger(__name__)

GOAL_MATCH_THRESHOLD = float(os.getenv("BRAIN_DUMP_GOAL_MATCH_THRESHOLD", "0.85"))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if not mag_a or not mag_b:
        return 0.0
    return dot / (mag_a * mag_b)


def suggest_goal_link_for_brain_dump_item(
    db: Client,
    user_id: str,
    item_text: str,
    *,
    threshold: float | None = None,
) -> dict | None:
    """
    Suggest linking a brain-dump item to an existing active goal when semantic
    similarity is high enough. Returns None when the item should stand alone.
    """
    threshold = GOAL_MATCH_THRESHOLD if threshold is None else threshold
    text = (item_text or "").strip()
    if not text:
        return None

    try:
        embedding = embed_text(text)
        rows = (
            db.rpc(
                "match_user_goals",
                {
                    "p_user_id": user_id,
                    "p_embedding": embedding,
                    "p_match_count": 3,
                },
            )
            .execute()
            .data
        ) or []
    except Exception as exc:  # noqa: BLE001 - suggestions must not block brain dump
        logger.warning("Brain-dump goal match failed user_id=%s: %s", user_id, str(exc)[:200])
        return None

    best = None
    for row in rows:
        similarity = row.get("similarity")
        if similarity is None and row.get("embedding") is not None:
            similarity = _cosine_similarity(embedding, row["embedding"])
        try:
            score = float(similarity)
        except (TypeError, ValueError):
            continue
        if best is None or score > best["similarity"]:
            best = {
                "goal_id": row.get("goal_id") or row.get("id"),
                "goal_title": row.get("title"),
                "similarity": score,
                "suggestion": "link_existing_goal",
            }

    if best and best["similarity"] >= threshold:
        return best
    return None


def annotate_brain_dump_goal_matches(
    db: Client,
    user_id: str,
    items: list[dict],
    *,
    threshold: float | None = None,
) -> list[dict]:
    annotated: list[dict] = []
    for item in items:
        title = str(item.get("title") or "").strip()
        suggestion = suggest_goal_link_for_brain_dump_item(
            db, user_id, title, threshold=threshold
        )
        if suggestion:
            annotated.append({**item, **suggestion})
        else:
            annotated.append({**item, "suggestion": "create_new_or_unlinked"})
    return annotated


def _parse_log_date(logged_at: str | None) -> date | None:
    if not logged_at:
        return None
    try:
        return datetime.fromisoformat(logged_at.replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return logged_at[:10] if len(logged_at) >= 10 else None


def weekday_energy_baselines(db: Client, user_id: str, lookback_days: int = 28) -> dict[int, float]:
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    resp = (
        db.table("energy_logs")
        .select("confirmed_score, logged_at")
        .eq("user_id", user_id)
        .gte("logged_at", since)
        .execute()
    )
    buckets: dict[int, list[int]] = defaultdict(list)
    for row in resp.data or []:
        score = row.get("confirmed_score")
        d = _parse_log_date(row.get("logged_at"))
        if score is None or d is None:
            continue
        buckets[d.weekday()].append(int(score))

    return {wd: (sum(scores) / len(scores) if scores else 5.0) for wd, scores in ((i, buckets.get(i, [])) for i in range(7))}


def forecast_energy_landscape(
    db: Client,
    user_id: str,
    profile: dict | None,
    *,
    horizon_days: int = 14,
) -> list[dict]:
    profile = profile or {}
    baselines = weekday_energy_baselines(db, user_id)
    today = date.today()

    today_meetings = 0
    today_events = 0
    refresh_token = (
        get_google_refresh_token(user_id, db)
        if profile.get("google_calendar_connected")
        else None
    )
    if refresh_token:
        try:
            events = get_today_events(refresh_token)
            summary = summarize_events(events)
            today_meetings = summary.get("total_meeting_minutes", 0)
            today_events = summary.get("event_count", 0)
        except CalendarSyncError as exc:
            logger.warning(
                "Calendar unavailable for energy forecast user_id=%s code=%s: %s",
                user_id,
                exc.code.value,
                str(exc.cause or exc)[:200],
            )

    landscape: list[dict] = []
    for offset in range(horizon_days):
        d = today + timedelta(days=offset)
        base = baselines.get(d.weekday(), 5.0)
        if offset == 0:
            penalty = min(4.0, (today_meetings / 60.0) * 1.2 + today_events * 0.3)
            capacity = max(1, min(10, round(base - penalty)))
            meetings, events = today_meetings, today_events
        else:
            capacity = max(1, min(10, round(base)))
            meetings, events = 0, 0
        landscape.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%A"),
            "predicted_capacity": int(capacity),
            "meeting_minutes": meetings,
            "meeting_count": events,
            "is_today": offset == 0,
        })
    return landscape


def assign_milestones_to_days(milestones: list[dict], landscape: list[dict]) -> list[dict]:
    if not milestones or not landscape:
        return milestones

    ordered = sorted(
        enumerate(milestones),
        key=lambda pair: (-int(pair[1].get("cognitive_load_score") or 5), pair[0]),
    )
    days_by_capacity = sorted(landscape, key=lambda d: (-d["predicted_capacity"], d["date"]))
    heavy_days: set[str] = set()
    day_assignments: dict[str, int] = defaultdict(int)
    scheduled: dict[int, dict] = {}

    for idx, milestone in ordered:
        load = int(milestone.get("cognitive_load_score") or 5)
        picked = None
        for day in days_by_capacity:
            day_date = day["date"]
            if load >= 7 and day_date in heavy_days:
                continue
            if day["predicted_capacity"] >= max(1, load - 2):
                picked = day
                break
        if not picked:
            picked = min(landscape, key=lambda d: (day_assignments[d["date"]], d["date"]))
        scheduled[idx] = {
            **milestone,
            "scheduled_date": picked["date"],
            "scheduled_capacity": picked["predicted_capacity"],
        }
        day_assignments[picked["date"]] += 1
        if load >= 7:
            heavy_days.add(picked["date"])

    return [scheduled[i] for i in sorted(scheduled.keys())]


def compute_milestone_progress(db: Client, milestone_id: str) -> int:
    resp = (
        db.table("tasks")
        .select("status")
        .eq("milestone_id", milestone_id)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return 0
    done = sum(1 for r in rows if r.get("status") == "completed")
    return round(done / len(rows) * 100)


def sync_milestone_progress(db: Client, milestone_id: str) -> int:
    pct = compute_milestone_progress(db, milestone_id)
    try:
        updates: dict = {"progress_percent": pct}
        if pct >= 100:
            updates["status"] = "completed"
            updates["completed_at"] = datetime.now(timezone.utc).isoformat()
        elif pct > 0:
            updates["status"] = "active"
        db.table("milestones").update(updates).eq("id", milestone_id).execute()
    except Exception:
        pass
    return pct


def compute_goal_progress(db: Client, goal_id: str) -> int:
    try:
        resp = (
            db.table("milestones")
            .select("status, progress_percent")
            .eq("goal_id", goal_id)
            .execute()
        )
        rows = resp.data or []
        if rows:
            if all(r.get("status") == "completed" for r in rows):
                return 100
            pcts = [int(r.get("progress_percent") or 0) for r in rows]
            return round(sum(pcts) / len(pcts))
    except Exception:
        pass

    # Legacy: is_milestone task rows
    resp = (
        db.table("tasks")
        .select("status")
        .eq("goal_id", goal_id)
        .eq("is_milestone", True)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return 0
    done = sum(1 for r in rows if r.get("status") == "completed")
    return round(done / len(rows) * 100)


def sync_goal_progress(db: Client, goal_id: str) -> int:
    pct = compute_goal_progress(db, goal_id)
    try:
        db.table("goals").update({"progress_percent": pct}).eq("id", goal_id).execute()
    except Exception:
        pass
    return pct


def _insert_milestone_tasks(
    db: Client,
    user_id: str,
    goal_id: str,
    milestone_id: str,
    milestone_spec: dict,
    profile: dict,
    goal_title: str | None = None,
) -> list[dict]:
    """Create child tasks under a milestone entity."""
    load = max(1, min(10, int(milestone_spec.get("cognitive_load_score") or 6)))
    est = int(milestone_spec.get("estimated_minutes") or 90)
    try:
        child_specs = decompose_milestone_tasks(
            milestone_spec["title"], load, est, profile, goal_title=goal_title
        )
    except Exception:
        child_specs = [{
            "title": milestone_spec["title"],
            "cognitive_load_score": load,
            "estimated_minutes": est,
        }]

    inserted: list[dict] = []
    for i, spec in enumerate(child_specs[:6]):
        payload = {
            "user_id": user_id,
            "goal_id": goal_id,
            "milestone_id": milestone_id,
            "title": spec["title"][:200],
            "cognitive_load_score": max(1, min(10, int(spec.get("cognitive_load_score") or load))),
            "estimated_minutes": int(spec.get("estimated_minutes") or 30),
            "source": "milestone_task",
            "status": "pending",
            "step_order": i + 1,
        }
        try:
            row = db.table("tasks").insert(payload).execute()
        except Exception:
            row = db.table("tasks").insert({
                k: v for k, v in payload.items()
                if k not in ("milestone_id", "estimated_minutes")
            }).execute()
        if row.data:
            inserted.append(row.data[0])
    return inserted


def insert_scheduled_milestones(
    db: Client,
    user_id: str,
    goal_id: str,
    milestones: list[dict],
    profile: dict | None,
    goal_title: str | None = None,
) -> dict:
    """Create milestone entities + child tasks, scheduled across the forecast horizon."""
    profile = profile or {}
    landscape = forecast_energy_landscape(db, user_id, profile)
    scheduled = assign_milestones_to_days(milestones, landscape)

    inserted_milestones: list[dict] = []
    inserted_tasks: list[dict] = []

    for i, m in enumerate(scheduled):
        ms_payload = {
            "user_id": user_id,
            "goal_id": goal_id,
            "title": m["title"][:200],
            "milestone_order": i + 1,
            "scheduled_date": m.get("scheduled_date"),
            "cognitive_load_score": max(1, min(10, int(m.get("cognitive_load_score") or 6))),
            "estimated_minutes": int(m.get("estimated_minutes") or 90),
            "status": "pending",
            "progress_percent": 0,
        }
        try:
            ms_row = db.table("milestones").insert(ms_payload).execute()
        except Exception:
            # Fallback: legacy milestone-as-task row
            legacy = db.table("tasks").insert({
                "user_id": user_id,
                "goal_id": goal_id,
                "title": m["title"][:200],
                "cognitive_load_score": ms_payload["cognitive_load_score"],
                "source": "goal_milestone",
                "status": "pending",
                "is_milestone": True,
                "milestone_order": i + 1,
                "scheduled_date": m.get("scheduled_date"),
                "estimated_minutes": ms_payload["estimated_minutes"],
            }).execute()
            if legacy.data:
                inserted_milestones.append({**legacy.data[0], "scheduled_date": m.get("scheduled_date")})
            continue

        if not ms_row.data:
            continue
        milestone = ms_row.data[0]
        milestone_id = milestone["id"]
        inserted_milestones.append({**milestone, "scheduled_date": m.get("scheduled_date")})

        children = _insert_milestone_tasks(
            db, user_id, goal_id, milestone_id, m, profile, goal_title=goal_title
        )
        inserted_tasks.extend(children)

    sync_goal_progress(db, goal_id)
    return {
        "inserted": len(inserted_milestones),
        "milestones": inserted_milestones,
        "tasks": inserted_tasks,
        "landscape": landscape,
    }


def insert_copilot_milestones(
    db: Client,
    user_id: str,
    milestones: list[dict],
    profile: dict | None = None,
) -> dict:
    """Create today's Co-Pilot milestones + child tasks (scheduled for today)."""
    today = date.today().isoformat()

    goal_resp = (
        db.table("goals")
        .select("id")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("created_at")
        .limit(1)
        .execute()
    )
    goal_id = goal_resp.data[0]["id"] if goal_resp.data else None

    inserted_milestones: list[dict] = []
    inserted_tasks: list[dict] = []

    for i, m in enumerate(milestones):
        ms_payload = {
            "user_id": user_id,
            "goal_id": goal_id,
            "title": m["title"][:200],
            "milestone_order": i + 1,
            "scheduled_date": today,
            "cognitive_load_score": max(1, min(10, int(m.get("cognitive_load_score") or 6))),
            "estimated_minutes": int(m.get("estimated_minutes") or 60),
            "status": "active",
            "progress_percent": 0,
        }
        try:
            ms_row = db.table("milestones").insert(ms_payload).execute()
        except Exception:
            for j, spec in enumerate(m.get("tasks") or []):
                row = db.table("tasks").insert({
                    "user_id": user_id,
                    "goal_id": goal_id,
                    "title": spec["title"][:200],
                    "cognitive_load_score": max(1, min(10, int(spec.get("cognitive_load_score") or 5))),
                    "source": "copilot_suggested",
                    "status": "pending",
                    "daily_assigned_date": today,
                    "step_order": j + 1,
                }).execute()
                if row.data:
                    inserted_tasks.append(row.data[0])
            continue

        if not ms_row.data:
            continue
        milestone = ms_row.data[0]
        milestone_id = milestone["id"]
        inserted_milestones.append(milestone)

        for j, spec in enumerate(m.get("tasks") or []):
            payload = {
                "user_id": user_id,
                "goal_id": goal_id,
                "milestone_id": milestone_id,
                "title": spec["title"][:200],
                "cognitive_load_score": max(1, min(10, int(spec.get("cognitive_load_score") or 5))),
                "estimated_minutes": int(spec.get("estimated_minutes") or 30),
                "source": "copilot_suggested",
                "status": "pending",
                "daily_assigned_date": today,
                "step_order": j + 1,
            }
            try:
                row = db.table("tasks").insert(payload).execute()
            except Exception:
                row = db.table("tasks").insert({
                    k: v for k, v in payload.items()
                    if k not in ("milestone_id", "estimated_minutes", "daily_assigned_date")
                }).execute()
            if row.data:
                inserted_tasks.append(row.data[0])

    if goal_id:
        sync_goal_progress(db, goal_id)

    return {
        "inserted_milestones": len(inserted_milestones),
        "inserted_tasks": len(inserted_tasks),
        "milestones": inserted_milestones,
        "tasks": inserted_tasks,
    }


def task_is_due_for_today(task: dict, today: date | None = None) -> bool:
    today = today or date.today()
    if task.get("milestone_id"):
        return True  # daily scheduler gates milestone children
    if task.get("is_milestone"):
        sd = task.get("scheduled_date")
        if not sd:
            return False
        try:
            return date.fromisoformat(str(sd)[:10]) <= today
        except ValueError:
            return False
    sd = task.get("scheduled_date")
    if not sd:
        return True
    try:
        return date.fromisoformat(str(sd)[:10]) <= today
    except ValueError:
        return True


def fetch_goals_with_milestones(db: Client, user_id: str) -> list[dict]:
    goals_resp = (
        db.table("goals")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("created_at")
        .execute()
    )
    goals = goals_resp.data or []
    if not goals:
        return []

    milestone_rows: list[dict] = []
    try:
        ms_resp = (
            db.table("milestones")
            .select("*")
            .eq("user_id", user_id)
            .order("milestone_order")
            .execute()
        )
        milestone_rows = ms_resp.data or []
    except Exception:
        pass

    tasks_by_milestone: dict[str, list] = defaultdict(list)
    if milestone_rows:
        ms_ids = [m["id"] for m in milestone_rows]
        try:
            tasks_resp = (
                db.table("tasks")
                .select("id, milestone_id, title, status, step_order, estimated_minutes, cognitive_load_score, scheduled_block_start")
                .eq("user_id", user_id)
                .in_("milestone_id", ms_ids)
                .execute()
            )
            for t in tasks_resp.data or []:
                mid = t.get("milestone_id")
                if mid:
                    tasks_by_milestone[mid].append(t)
        except Exception:
            pass

    if not milestone_rows:
        try:
            legacy = (
                db.table("tasks")
                .select("*")
                .eq("user_id", user_id)
                .eq("is_milestone", True)
                .execute()
            )
            milestone_rows = legacy.data or []
        except Exception:
            milestone_rows = []

    by_goal: dict[str, list] = defaultdict(list)
    for m in milestone_rows:
        gid = m.get("goal_id")
        if gid:
            mid = m.get("id")
            if mid and mid in tasks_by_milestone:
                m = {**m, "tasks": sorted(
                    tasks_by_milestone[mid],
                    key=lambda t: (t.get("step_order") or 999),
                )}
            by_goal[gid].append(m)

    today = date.today().isoformat()
    result = []
    for g in goals:
        milestones = sorted(
            by_goal.get(g["id"], []),
            key=lambda m: (m.get("milestone_order") or 999, m.get("created_at") or ""),
        )
        for m in milestones:
            m["is_future"] = bool(
                m.get("scheduled_date") and str(m["scheduled_date"])[:10] > today
            )
            if "progress_percent" not in m or m.get("progress_percent") is None:
                if m.get("id") and tasks_by_milestone.get(m["id"]):
                    m["progress_percent"] = compute_milestone_progress(db, m["id"])
        pct = g.get("progress_percent")
        if pct is None and milestones:
            pct = compute_goal_progress(db, g["id"])
        result.append({**g, "progress_percent": pct or 0, "milestones": milestones})
    return result
