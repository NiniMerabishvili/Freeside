"""Per-user calibration for AI energy suggestions."""
from __future__ import annotations

from supabase import Client


def energy_bias_for_user(db: Client, user_id: str, *, limit: int = 30) -> float:
    rows = (
        db.table("energy_logs")
        .select("ai_suggested_score, confirmed_score, logged_at")
        .eq("user_id", user_id)
        .order("logged_at", desc=True)
        .limit(limit)
        .execute()
        .data
    ) or []
    deltas: list[float] = []
    for row in rows:
        suggested = row.get("ai_suggested_score")
        confirmed = row.get("confirmed_score")
        if suggested is None or confirmed is None:
            continue
        deltas.append(float(confirmed) - float(suggested))
    if not deltas:
        return 0.0
    return round(sum(deltas) / len(deltas), 3)


def _score_to_level(score: int) -> str:
    if score >= 7:
        return "high"
    if score >= 4:
        return "balanced"
    return "low"


def apply_energy_bias(suggestion: dict, bias: float) -> dict:
    adjusted = max(1, min(10, round(float(suggestion["suggested_score"]) + bias)))
    return {
        **suggestion,
        "raw_suggested_score": suggestion["suggested_score"],
        "calibration_bias": bias,
        "suggested_score": adjusted,
        "suggested_level": _score_to_level(adjusted),
    }
