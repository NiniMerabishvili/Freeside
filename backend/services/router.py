"""
Cognitive Load Contextual Scheduling (CLCS) — v3

Energy-aware task routing algorithm (see thesis §3.2). v3 keeps the original
5-step backbone and extends it with four behaviourally-grounded refinements
(all bounded, deterministic, and backward compatible):

  Step 1 — Effective capacity: raw energy + peak-hour boost (+1), capped at 10.
            Implements Mark et al. (2014) — within-day performance peaks are real.
            v3 also computes a graded `peak_factor` (0–1) used only for
            fine-grained priority shaping, not for the reported capacity integer.

  Step 2 — Delta: delta = task.cognitive_load_score − effective_capacity
            Positive  → task demands more than current capacity (risk of overload)
            Negative  → task is easier than capacity (still shown, lower priority)

  Step 3 — Compatibility gate: delta ≤ tolerance → active · else rerouted.
            Base tolerance is 2 (a healthy stretch). v3 grows tolerance with the
            task's age (Temporal Motivation Theory, Steel 2007): a task deferred
            for D days gains +1 tolerance per day (capped +3), so nothing stays
            stuck behind an energy wall indefinitely.

  Step 4 — Priority score: priority = 10 − |delta|, then bounded boosts:
            + goal alignment (linked to an active goal)      → the thesis anchors
              everything to goals, so goal work outranks noise.
            + explicit day-plan focus / ClickUp / Co-Pilot source.
            + low-energy quick-win momentum (Self-Determination Theory / behavioural
              activation): when energy is low, one genuinely light task is lifted so
              the user can start and build momentum.

  Step 5 — Output order: active tasks by a deterministic sort key
            (priority desc, goal-aligned first, shorter tasks first, title),
            rerouted ascending by unlock_score (closest-to-unlock first).

This remains a pure function — same inputs → same output (inject `now` for tests).
"""
from __future__ import annotations

from datetime import datetime, time, timezone


_PEAK_WINDOWS: dict[str, tuple[time, time]] = {
    "early_bird": (time(5, 0),  time(9, 0)),
    "morning":    (time(6, 0),  time(12, 0)),
    "afternoon":  (time(12, 0), time(17, 0)),
    "evening":    (time(17, 0), time(21, 0)),
    "night":      (time(21, 0), time(23, 59)),
}

# Bounded tuning constants — kept explicit so the thesis can cite exact values.
_BASE_TOLERANCE = 2          # healthy stretch above capacity (delta ≤ 2 → active)
_MAX_AGE_TOLERANCE = 3       # extra tolerance a stale task can accumulate
_GOAL_ALIGN_BOOST = 2        # priority boost for tasks linked to an active goal
_FOCUS_BOOST = 3             # priority boost for explicit day-plan focus titles
_SOURCE_BOOST = 2            # priority boost for ClickUp / Co-Pilot sourced tasks
_QUICK_WIN_BOOST = 2         # low-energy momentum boost for one light task
_LOW_ENERGY_THRESHOLD = 3    # energy at/below which quick-win momentum kicks in
_QUICK_WIN_MAX_LOAD = 3      # a task must be this light to count as a quick win


def _in_peak_window(peak_focus_time: str | None, now: datetime) -> bool:
    """Return True if `now` falls inside the user's stated peak-focus window."""
    if not peak_focus_time:
        return False
    window = _PEAK_WINDOWS.get(peak_focus_time.lower().strip())
    if window is None:
        return False
    return window[0] <= now.time() <= window[1]


def _peak_factor(peak_focus_time: str | None, now: datetime) -> float:
    """
    Graded proximity (0–1) to the centre of the peak window.

    1.0 at the exact centre, tapering linearly to 0 at the window edges,
    0 outside the window. Used for fine priority shaping only.
    """
    if not peak_focus_time:
        return 0.0
    window = _PEAK_WINDOWS.get(peak_focus_time.lower().strip())
    if window is None:
        return 0.0
    start_min = window[0].hour * 60 + window[0].minute
    end_min = window[1].hour * 60 + window[1].minute
    now_min = now.hour * 60 + now.minute
    if not (start_min <= now_min <= end_min):
        return 0.0
    centre = (start_min + end_min) / 2
    half_span = max(1, (end_min - start_min) / 2)
    return max(0.0, 1.0 - abs(now_min - centre) / half_span)


def _task_age_days(task: dict, now: datetime) -> int:
    """Whole days since the task was created (0 if unknown/unparseable)."""
    created = task.get("created_at")
    if not created:
        return 0
    try:
        created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return 0
    if created_dt.tzinfo is None:
        created_dt = created_dt.replace(tzinfo=timezone.utc)
    ref = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return max(0, (ref - created_dt).days)


def route_tasks(
    tasks: list[dict],
    energy_score: int,
    peak_focus_time: str | None = None,
    # legacy compat — energy_level label is no longer used for routing
    energy_level: str | None = None,
    focus_titles: list[str] | None = None,
    now: datetime | None = None,
) -> dict:
    """
    Run CLCS routing.

    Args:
        tasks:           Pending task dicts from Supabase.
        energy_score:    User-confirmed energy (1-10).
        peak_focus_time: 'morning' | 'afternoon' | 'evening' | 'night' | None
        focus_titles:    Titles the day-plan flagged as today's focus.
        now:             Injectable clock for deterministic tests.

    Returns a dict:
        {
          "effective_capacity": int,
          "peak_boost":         bool,
          "peak_factor":        float,   # 0–1 proximity to peak centre
          "tasks":              list,    # active first, rerouted after
          "active_count":       int,
          "rerouted_count":     int,
        }

    Each task is augmented with:
        visible, delta, priority_score, reroute_reason, unlock_score,
        goal_aligned, is_quick_win
    """
    now = now or datetime.now()

    # ── Step 1: Effective capacity ────────────────────────────────────────────
    peak_boost         = _in_peak_window(peak_focus_time, now)
    peak_factor        = _peak_factor(peak_focus_time, now)
    effective_capacity = min(energy_score + (1 if peak_boost else 0), 10)

    low_energy   = energy_score <= _LOW_ENERGY_THRESHOLD
    focus_lower  = [f.lower() for f in (focus_titles or []) if f]

    active:   list[dict] = []
    rerouted: list[dict] = []

    for task in tasks:
        load  = int(task.get("cognitive_load_score") or 5)
        delta = load - effective_capacity  # ── Step 2 ──

        # ── Step 3: Age-aware compatibility gate ──────────────────────────────
        age_days  = _task_age_days(task, now)
        tolerance = _BASE_TOLERANCE + min(age_days, _MAX_AGE_TOLERANCE)

        goal_aligned = bool(task.get("goal_id"))

        if delta <= tolerance:
            # ── Step 4: Priority score ────────────────────────────────────────
            priority = 10 - abs(delta)

            # Graded peak nudge: near the peak centre, reward well-matched work.
            if peak_factor > 0 and delta >= -1:
                priority += round(peak_factor)

            title_lower = (task.get("title") or "").lower()
            source = task.get("source") or ""
            if focus_lower and any(
                fl in title_lower or title_lower in fl for fl in focus_lower
            ):
                priority += _FOCUS_BOOST
            elif source in ("clickup", "copilot_suggested"):
                priority += _SOURCE_BOOST

            if goal_aligned:
                priority += _GOAL_ALIGN_BOOST

            is_quick_win = low_energy and load <= _QUICK_WIN_MAX_LOAD
            if is_quick_win:
                priority += _QUICK_WIN_BOOST

            active.append({
                **task,
                "visible":        True,
                "delta":          delta,
                "priority_score": max(0, min(10, priority)),
                "goal_aligned":   goal_aligned,
                "is_quick_win":   is_quick_win,
                "reroute_reason": None,
                "unlock_score":   None,
            })
        else:
            # Minimum energy the user needs for this task to pass the base gate.
            unlock_score = max(1, load - _BASE_TOLERANCE)
            if age_days > 0:
                reason = (
                    f"Needs energy {unlock_score}+/10 · waiting {age_days}d, "
                    f"surfaces sooner as it ages"
                )
            else:
                reason = f"Needs energy {unlock_score}+/10 · will re-evaluate tomorrow"
            rerouted.append({
                **task,
                "visible":        False,
                "delta":          delta,
                "priority_score": 0,
                "goal_aligned":   goal_aligned,
                "is_quick_win":   False,
                "reroute_reason": reason,
                "unlock_score":   unlock_score,
            })

    # ── Step 5: Deterministic ordering ──────────────────────────────────────────
    # Active: highest priority, then goal-aligned, then shorter tasks (quick to
    # finish), then title for stability.
    active.sort(
        key=lambda t: (
            -t["priority_score"],
            not t["goal_aligned"],
            int(t.get("estimated_minutes") or 999),
            (t.get("title") or "").lower(),
        )
    )
    # Rerouted: closest-to-unlock first, then goal-aligned, then title.
    rerouted.sort(
        key=lambda t: (
            t.get("unlock_score") or 99,
            not t["goal_aligned"],
            (t.get("title") or "").lower(),
        )
    )

    return {
        "effective_capacity": effective_capacity,
        "peak_boost":         peak_boost,
        "peak_factor":        round(peak_factor, 2),
        "tasks":              active + rerouted,
        "active_count":       len(active),
        "rerouted_count":     len(rerouted),
    }
