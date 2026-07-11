#!/usr/bin/env python
"""Train the baseline burnout logistic regression model.

Uses weak labels from services.burnout_labels because survey-backed clinical
labels do not exist yet. If enough Supabase historical windows are available,
they can be added later; this first baseline trains on synthetic windows that
span plausible Freeside behavior ranges and validates the full serialization
path.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from services.burnout_labels import burnout_label, burnout_label_score
from services.burnout_model import MODEL_FEATURES, MODEL_VERSION


def _synthetic_features(n: int = 600, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        energy_slope = rng.uniform(-0.45, 0.18)
        reroute_rate = rng.betavariate(1.6, 4.5)
        abandonment = rng.betavariate(1.4, 5.5)
        sleep_slope = rng.uniform(-0.25, 0.18)
        avg_energy = max(1.0, min(10.0, rng.gauss(6.2 + energy_slope * 4, 1.2)))
        avg_sleep = max(3.5, min(9.5, rng.gauss(7.0 + sleep_slope * 2, 0.8)))
        row = {
            "avg_confirmed_energy": avg_energy,
            "energy_trend_slope": energy_slope,
            "reroute_rate": reroute_rate,
            "task_abandonment_rate": abandonment,
            "avg_hours_slept": avg_sleep,
            "sleep_duration_trend_slope": sleep_slope,
            "sleep_duration_stddev": rng.uniform(0.05, 1.8),
            "avg_rested_score": max(1.0, min(5.0, rng.gauss(3.5 + sleep_slope, 0.7))),
            "rested_score_trend_slope": rng.uniform(-0.12, 0.1),
            "data_coverage_days": rng.randint(3, 14),
            "missing_days": rng.randint(0, 11),
        }
        row["weak_label_score"] = burnout_label_score(row)
        row["burnout_risk"] = burnout_label(row)
        rows.append(row)
    return rows


def main() -> None:
    rows = _synthetic_features()
    x = [[float(row.get(name) or 0.0) for name in MODEL_FEATURES] for row in rows]
    y = [row["burnout_risk"] for row in rows]

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.25, random_state=7, stratify=y
    )
    model = Pipeline([
        ("scale", StandardScaler()),
        ("logreg", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    model.fit(x_train, y_train)
    pred = model.predict(x_test)
    proba = model.predict_proba(x_test)[:, 1]
    metrics = {
        "training_source": "synthetic_weak_labels",
        "rows": len(rows),
        "positive_rate": round(sum(y) / len(y), 4),
        "accuracy": round(accuracy_score(y_test, pred), 4),
        "precision": round(precision_score(y_test, pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, proba), 4),
    }

    out_dir = ROOT / "backend" / "ml" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": model,
        "features": MODEL_FEATURES,
        "model_version": MODEL_VERSION,
        "label_formula": "0.45*energy_decline + 0.30*reroute + 0.25*abandonment >= 0.55",
        "metrics": metrics,
    }, out_dir / "burnout_logreg.joblib")
    (out_dir / "burnout_logreg_metrics.json").write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
