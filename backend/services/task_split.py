"""Energy-aware task splitting — overloaded tasks become routable subtasks."""
from __future__ import annotations

from supabase import Client

from services.ai import split_task_for_energy
from services.db_compat import is_missing_column_error
from services.router import route_tasks


def _sort_children(children: list[dict]) -> list[dict]:
    """Order subtasks by step_order when present, else by created_at."""
    return sorted(
        children,
        key=lambda c: (
            c.get("step_order") is None,
            c.get("step_order") if c.get("step_order") is not None else 999,
            c.get("created_at") or "",
        ),
    )


def _would_reroute(load: int, effective_capacity: int) -> bool:
    return load - effective_capacity > 2


def _fetch_pending_children(db: Client, parent_id: str) -> list[dict]:
    resp = (
        db.table("tasks")
        .select("*")
        .eq("parent_task_id", parent_id)
        .eq("status", "pending")
        .execute()
    )
    return _sort_children(resp.data or [])


def _fetch_all_children(db: Client, parent_id: str) -> list[dict]:
    resp = (
        db.table("tasks")
        .select("*")
        .eq("parent_task_id", parent_id)
        .execute()
    )
    return _sort_children(resp.data or [])


def parent_progress_percent(db: Client, parent_id: str) -> int:
    children = _fetch_all_children(db, parent_id)
    if not children:
        return 0
    done = sum(1 for c in children if c.get("status") == "completed")
    return round(done / len(children) * 100)


def _parent_meta(db: Client, parent: dict) -> dict:
    return {
        "parent_id": parent["id"],
        "parent_title": parent["title"],
        "parent_load": int(parent.get("cognitive_load_score") or 5),
        "progress_percent": parent_progress_percent(db, parent["id"]),
    }


def _create_subtasks(
    db: Client,
    user_id: str,
    parent: dict,
    energy_score: int,
    effective_capacity: int,
    profile: dict,
) -> list[dict]:
    parent_load = int(parent.get("cognitive_load_score") or 5)
    specs = split_task_for_energy(
        parent["title"],
        parent_load,
        energy_score,
        effective_capacity,
        profile,
    )

    inserted: list[dict] = []
    for spec in specs:
        payload = {
            "user_id": user_id,
            "title": spec["title"],
            "cognitive_load_score": spec["cognitive_load_score"],
            "parent_task_id": parent["id"],
            "source": "ai_subtask",
            "goal_id": parent.get("goal_id"),
        }
        try:
            row = db.table("tasks").insert({
                **payload,
                "step_order": spec["step_order"],
            }).execute()
        except Exception as exc:
            if not is_missing_column_error(exc):
                raise
            row = db.table("tasks").insert(payload).execute()
        if row.data:
            item = row.data[0]
            if item.get("step_order") is None:
                item = {**item, "step_order": spec["step_order"]}
            inserted.append(item)

    if inserted:
        db.table("tasks").update({"status": "active"}).eq("id", parent["id"]).execute()
        try:
            db.table("copilot_logs").insert({
                "user_id": user_id,
                "message_type": "break_down",
                "task_id": parent["id"],
            }).execute()
        except Exception:
            pass

    return inserted


def ensure_split_children(
    db: Client,
    user_id: str,
    parent: dict,
    energy_score: int,
    effective_capacity: int,
    profile: dict,
) -> list[dict]:
    """Return pending subtasks for a parent, creating them on first reroute."""
    existing = _fetch_pending_children(db, parent["id"])
    if existing:
        return existing
    return _create_subtasks(db, user_id, parent, energy_score, effective_capacity, profile)


def prepare_routing_pool(
    db: Client,
    user_id: str,
    pending_tasks: list[dict],
    active_parents: list[dict],
    energy_score: int,
    effective_capacity: int,
    profile: dict,
) -> tuple[list[dict], dict[str, dict]]:
    """
    Expand overloaded top-level tasks into subtasks for CLCS routing.

    Returns (routable_tasks, parent_meta_by_id).
    """
    children_by_parent: dict[str, list[dict]] = {}
    for t in pending_tasks:
        pid = t.get("parent_task_id")
        if pid:
            children_by_parent.setdefault(pid, []).append(t)

    top_level = [t for t in pending_tasks if not t.get("parent_task_id")]
    top_level_ids = {t["id"] for t in top_level}
    for parent in active_parents:
        if parent["id"] not in top_level_ids:
            top_level.append(parent)

    routable: list[dict] = []
    parent_meta: dict[str, dict] = {}

    for task in top_level:
        load = int(task.get("cognitive_load_score") or 5)
        already_split = task["id"] in children_by_parent or task.get("status") == "active"
        needs_split = _would_reroute(load, effective_capacity)

        if already_split or needs_split:
            children = children_by_parent.get(task["id"])
            if not children:
                children = ensure_split_children(
                    db, user_id, task, energy_score, effective_capacity, profile
                )
            if children:
                parent_meta[task["id"]] = _parent_meta(db, task)
                routable.extend(children)
            elif needs_split:
                # Split failed — keep parent as-is for routing
                routable.append(task)
            continue

        routable.append(task)

    return routable, parent_meta


def enrich_routed_tasks(
    routed_tasks: list[dict],
    parent_meta: dict[str, dict],
) -> list[dict]:
    """Attach parent context and blocked flag to routed subtasks."""
    enriched = []
    for task in routed_tasks:
        pid = task.get("parent_task_id")
        item = {**task}
        if pid and pid in parent_meta:
            meta = parent_meta[pid]
            item["parent_title"] = meta["parent_title"]
            item["progress_percent"] = meta["progress_percent"]
            item["is_blocked"] = task.get("visible") is False
        enriched.append(item)
    return enriched


def maybe_complete_parent(db: Client, user_id: str, parent_id: str | None) -> None:
    """Mark parent complete when all subtasks are done."""
    if not parent_id:
        return
    children = _fetch_all_children(db, parent_id)
    if not children:
        return
    if all(c.get("status") == "completed" for c in children):
        from datetime import datetime, timezone
        db.table("tasks").update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", parent_id).eq("user_id", user_id).execute()


def route_with_splits(
    db: Client,
    user_id: str,
    pending_tasks: list[dict],
    active_parents: list[dict],
    energy_score: int,
    peak_focus_time: str | None,
    profile: dict,
    focus_titles: list[str] | None = None,
) -> dict:
    """Run CLCS after expanding overloaded tasks into subtasks."""
    preview = route_tasks(
        [t for t in pending_tasks if not t.get("parent_task_id")],
        energy_score,
        peak_focus_time,
        focus_titles=focus_titles,
    )
    effective_capacity = preview["effective_capacity"]

    pool, parent_meta = prepare_routing_pool(
        db, user_id, pending_tasks, active_parents, energy_score, effective_capacity, profile
    )

    if not pool:
        return {
            **preview,
            "tasks": [],
            "parent_groups": list(parent_meta.values()),
        }

    result = route_tasks(pool, energy_score, peak_focus_time, focus_titles=focus_titles)
    result["tasks"] = enrich_routed_tasks(result["tasks"], parent_meta)
    result["parent_groups"] = list(parent_meta.values())
    return result
