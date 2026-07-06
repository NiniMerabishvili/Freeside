"""
Cognitive Load Contextual Scheduling (CLCS) — v2

5-step energy-aware task routing algorithm (see thesis §3.2):

  Step 1 — Effective capacity: raw energy + peak-hour boost (+1), capped at 10.
            Implements Mark et al. (2014) — within-day performance peaks are real.

  Step 2 — Delta: delta = task.cognitive_load_score − effective_capacity
            Positive  → task demands more than current capacity (risk of overload)
            Negative  → task is easier than capacity (still shown, lower priority)

  Step 3 — Compatibility gate: delta ≤ 2 → active · delta > 2 → rerouted
            A stretch of ≤ 2 points is allowed (healthy challenge without overload).

  Step 4 — Priority score: priority = 10 − |delta|
            Maximum (10) when load == capacity: the optimal challenge point.
            Drops symmetrically for tasks too easy OR too hard.

  Step 5 — Output order: active tasks descending by priority_score,
            rerouted ascending by unlock_score (closest-to-unlock first).

This is a pure function — same inputs → same output. Fully testable.
"""
from __future__ import annotations
from datetime import datetime, time


_PEAK_WINDOWS: dict[str, tuple[time, time]] = {
    "early_bird": (time(5, 0),  time(9, 0)),
    "morning":    (time(6, 0),  time(12, 0)),
    "afternoon":  (time(12, 0), time(17, 0)),
    "evening":    (time(17, 0), time(21, 0)),
    "night":      (time(21, 0), time(23, 59)),
}


def _in_peak_window(peak_focus_time: str | None) -> bool:
    """Return True if now falls inside the user's stated peak-focus window."""
    if not peak_focus_time:
        return False
    now    = datetime.now().time()
    window = _PEAK_WINDOWS.get(peak_focus_time.lower().strip())
    if window is None:
        return False
    return window[0] <= now <= window[1]


def route_tasks(
    tasks: list[dict],
    energy_score: int,
    peak_focus_time: str | None = None,
    # legacy compat — energy_level label is no longer used for routing
    energy_level: str | None = None,
    focus_titles: list[str] | None = None,
) -> dict:
    """
    Run CLCS routing.

    Args:
        tasks:           Pending task dicts from Supabase.
        energy_score:    User-confirmed energy (1-10).
        peak_focus_time: 'morning' | 'afternoon' | 'evening' | 'night' | None

    Returns a dict:
        {
          "effective_capacity": int,
          "peak_boost":         bool,
          "tasks":              list,    # active first, rerouted after
          "active_count":       int,
          "rerouted_count":     int,
        }

    Each task is augmented with:
        visible, delta, priority_score, reroute_reason, unlock_score
    """
    # ── Step 1: Effective capacity ────────────────────────────────────────────
    peak_boost         = _in_peak_window(peak_focus_time)
    effective_capacity = min(energy_score + (1 if peak_boost else 0), 10)

    active:   list[dict] = []
    rerouted: list[dict] = []

    focus_lower = [f.lower() for f in (focus_titles or []) if f]

    for task in tasks:
        load  = int(task.get("cognitive_load_score") or 5)

        # ── Step 2: Delta ─────────────────────────────────────────────────────
        delta = load - effective_capacity

        # ── Step 3: Gate ──────────────────────────────────────────────────────
        if delta <= 2:
            # ── Step 4: Priority score ────────────────────────────────────────
            priority_score = 10 - abs(delta)
            title_lower = (task.get("title") or "").lower()
            source = task.get("source") or ""
            if focus_lower and any(
                fl in title_lower or title_lower in fl for fl in focus_lower
            ):
                priority_score = min(10, priority_score + 3)
            elif source in ("clickup", "copilot_suggested"):
                priority_score = min(10, priority_score + 2)
            active.append({
                **task,
                "visible":        True,
                "delta":          delta,
                "priority_score": priority_score,
                "reroute_reason": None,
                "unlock_score":   None,
            })
        else:
            # Minimum energy the user needs for this task to pass the gate
            unlock_score = max(1, load - 2)
            rerouted.append({
                **task,
                "visible":        False,
                "delta":          delta,
                "priority_score": 0,
                "reroute_reason": f"Needs energy {unlock_score}+/10 · will re-evaluate tomorrow",
                "unlock_score":   unlock_score,
            })

    # ── Step 5: Sort ──────────────────────────────────────────────────────────
    active.sort(key=lambda t: -t["priority_score"])           # best match first
    rerouted.sort(key=lambda t: t.get("unlock_score") or 99)  # closest-to-unlock first

    return {
        "effective_capacity": effective_capacity,
        "peak_boost":         peak_boost,
        "tasks":              active + rerouted,
        "active_count":       len(active),
        "rerouted_count":     len(rerouted),
    }
