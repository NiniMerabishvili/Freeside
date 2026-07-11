"""Composite burnout label used for the baseline model.

Formula rationale:
- Falling energy is the strongest burnout proxy, so it gets 45% weight.
- Frequent rerouting means demand exceeds capacity, so it gets 30%.
- Task abandonment captures disengagement/overload, so it gets 25%.

Each component is normalized to 0..1 against a practical threshold:
- energy_trend_slope <= -0.25 points/day is high risk.
- reroute_rate >= 0.35 is high risk.
- task_abandonment_rate >= 0.30 is high risk.

burnout_risk_score =
    0.45 * normalized_energy_decline
  + 0.30 * normalized_reroute_rate
  + 0.25 * normalized_abandonment_rate

burnout_risk label = score >= 0.55.

This is a weak supervision label for a baseline logistic regression, not a
clinical diagnosis. It is intentionally transparent and easy to replace once
survey-backed labels are available.
"""
from __future__ import annotations

LABEL_THRESHOLD = 0.55


def _clamp01(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def burnout_label_score(features: dict) -> float:
    energy_slope = features.get("energy_trend_slope")
    reroute_rate = features.get("reroute_rate")
    abandonment_rate = features.get("task_abandonment_rate")

    energy_decline = _clamp01((-(energy_slope or 0.0)) / 0.25)
    reroute = _clamp01((reroute_rate or 0.0) / 0.35)
    abandonment = _clamp01((abandonment_rate or 0.0) / 0.30)
    return round(0.45 * energy_decline + 0.30 * reroute + 0.25 * abandonment, 6)


def burnout_label(features: dict) -> int:
    return int(burnout_label_score(features) >= LABEL_THRESHOLD)
