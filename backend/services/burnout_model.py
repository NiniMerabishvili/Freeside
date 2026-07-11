"""Load and run the baseline burnout model."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
from dotenv import load_dotenv
from supabase import Client

from services.burnout_labels import burnout_label_score
from services.ml_features import build_user_feature_window

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

MODEL_FEATURES = [
    "avg_confirmed_energy",
    "energy_trend_slope",
    "reroute_rate",
    "task_abandonment_rate",
    "avg_hours_slept",
    "sleep_duration_trend_slope",
    "sleep_duration_stddev",
    "avg_rested_score",
    "rested_score_trend_slope",
    "data_coverage_days",
    "missing_days",
]
MODEL_VERSION = "burnout_logreg_v0.1"
MODEL_PATH = Path(os.getenv(
    "BURNOUT_MODEL_PATH",
    str(Path(__file__).parent.parent / "ml" / "artifacts" / "burnout_logreg.joblib"),
))

_model_bundle: dict | None = None


def _feature_vector(features: dict) -> list[float]:
    vector: list[float] = []
    for name in MODEL_FEATURES:
        value = features.get(name)
        vector.append(0.0 if value is None else float(value))
    return vector


def load_burnout_model() -> dict:
    global _model_bundle
    if _model_bundle is None:
        _model_bundle = joblib.load(MODEL_PATH)
    return _model_bundle


def predict_burnout_score(features: dict) -> dict:
    if not features.get("sufficient_data"):
        return {
            "score": None,
            "label": False,
            "model_version": MODEL_VERSION,
            "reason": features.get("insufficient_data_reason"),
        }

    bundle = load_burnout_model()
    model = bundle["model"]
    score = float(model.predict_proba([_feature_vector(features)])[0][1])
    return {
        "score": round(score, 5),
        "label": score >= 0.5,
        "model_version": bundle.get("model_version", MODEL_VERSION),
        "weak_label_score": burnout_label_score(features),
    }


def active_user_ids(db: Client) -> list[str]:
    rows = (
        db.table("profiles")
        .select("id")
        .eq("onboarding_completed", True)
        .execute()
        .data
    ) or []
    return [row["id"] for row in rows if row.get("id")]


def score_user(db: Client, user_id: str, *, window_days: int = 14) -> dict:
    features = build_user_feature_window(user_id, window_days=window_days, db=db)
    prediction = predict_burnout_score(features)
    payload: dict[str, Any] = {
        "user_id": user_id,
        "score": prediction["score"] if prediction["score"] is not None else 0.0,
        "label": prediction["label"],
        "model_version": prediction["model_version"],
        "feature_window_days": window_days,
        "features": features,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    db.table("burnout_scores").insert(payload).execute()
    return {**prediction, "user_id": user_id, "features": features}


def score_all_active_users(db: Client, *, window_days: int = 14) -> dict:
    results = []
    errors = []
    for user_id in active_user_ids(db):
        try:
            results.append(score_user(db, user_id, window_days=window_days))
        except Exception as exc:  # noqa: BLE001 - nightly job should continue per user
            errors.append({"user_id": user_id, "error": str(exc)[:300]})
    return {
        "status": "ok",
        "scored": len(results),
        "errors": errors,
        "model_version": MODEL_VERSION,
    }
