from __future__ import annotations

from datetime import datetime

from services.router import route_tasks


def test_task_above_effective_capacity_gets_deferred():
    result = route_tasks(
        [{"id": "t1", "title": "Write thesis chapter", "cognitive_load_score": 8}],
        energy_score=3,
        now=datetime(2026, 7, 11, 10, 0),
    )

    task = result["tasks"][0]
    assert result["active_count"] == 0
    assert result["rerouted_count"] == 1
    assert task["visible"] is False
    assert task["unlock_score"] == 6


def test_goal_aligned_tasks_get_priority_boost():
    result = route_tasks(
        [
            {"id": "generic", "title": "Clear inbox", "cognitive_load_score": 5},
            {
                "id": "goal",
                "title": "Draft launch plan",
                "cognitive_load_score": 5,
                "goal_id": "g1",
            },
        ],
        energy_score=5,
        now=datetime(2026, 7, 11, 10, 0),
    )

    assert result["tasks"][0]["id"] == "goal"
    assert result["tasks"][0]["goal_aligned"] is True
    assert result["tasks"][0]["priority_score"] > result["tasks"][1]["priority_score"]


def test_peak_hour_boost_applies_to_effective_capacity():
    result = route_tasks(
        [{"id": "t1", "title": "Build feature", "cognitive_load_score": 6}],
        energy_score=5,
        peak_focus_time="morning",
        now=datetime(2026, 7, 11, 9, 0),
    )

    assert result["peak_boost"] is True
    assert result["effective_capacity"] == 6
    assert result["tasks"][0]["delta"] == 0


def test_low_energy_day_defers_heavy_task_and_keeps_light_quick_win():
    result = route_tasks(
        [
            {"id": "heavy", "title": "Design architecture", "cognitive_load_score": 8},
            {"id": "light", "title": "File notes", "cognitive_load_score": 2},
        ],
        energy_score=2,
        now=datetime(2026, 7, 11, 10, 0),
    )

    by_id = {task["id"]: task for task in result["tasks"]}
    assert by_id["heavy"]["visible"] is False
    assert by_id["light"]["visible"] is True
    assert by_id["light"]["is_quick_win"] is True
