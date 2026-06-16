"""
Cognitive Load Task Router — The heart of the thesis.

Routes tasks based on the user's current energy level using cognitive load thresholds.
High energy → show all, prioritize deep work (7-10)
Balanced    → show 1-6, prioritize moderate (4-6)
Low         → show 1-3 only, prioritize light tasks
"""


def route_tasks(tasks: list, energy_level: str, energy_score: int) -> list:
    """
    Route tasks based on user's energy level.

    Args:
        tasks: List of task dicts from Supabase
        energy_level: 'high', 'balanced', or 'low'
        energy_score: 1-10 integer

    Returns:
        List of tasks with added 'priority', 'visible', and 'reroute_reason' fields,
        sorted by appropriateness for current energy.
    """
    thresholds = {
        "high": {"show": range(1, 11), "priority": range(7, 11)},
        "balanced": {"show": range(1, 7), "priority": range(4, 7)},
        "low": {"show": range(1, 4), "priority": range(1, 4)},
    }

    config = thresholds.get(energy_level, thresholds["balanced"])

    routed = []
    for task in tasks:
        load = task.get("cognitive_load_score", 5)
        if load in config["show"]:
            routed.append(
                {
                    **task,
                    "priority": "high" if load in config["priority"] else "normal",
                    "visible": True,
                    "reroute_reason": None,
                }
            )
        else:
            routed.append(
                {
                    **task,
                    "priority": "low",
                    "visible": False,
                    "reroute_reason": f"Cognitive load {load}/10 is too high for your current energy ({energy_level})",
                }
            )

    # Sort: visible first, then by priority, then by cognitive load
    # High energy: deep work first (descending load)
    # Low energy: light tasks first (ascending load)
    reverse_sort = energy_level == "high"
    routed.sort(
        key=lambda x: (
            not x["visible"],  # visible tasks first
            x["priority"] != "high",  # high priority first
            -x.get("cognitive_load_score", 5) if reverse_sort else x.get("cognitive_load_score", 5),
        )
    )

    return routed
