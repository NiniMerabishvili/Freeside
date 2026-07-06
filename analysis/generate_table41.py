#!/usr/bin/env python3
"""Print thesis Table 4.1 (paired t-tests) from baseline_survey.csv."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "baseline_survey.csv"


def cohens_d(pre: np.ndarray, post: np.ndarray) -> float:
    diff = pre - post
    sd = np.std(pre, ddof=1)
    return float(np.mean(diff) / sd) if sd > 0 else 0.0


def paired_row(label: str, pre: pd.Series, post: pd.Series) -> dict:
    df = pd.DataFrame({"pre": pre, "post": post}).dropna()
    pre_a = df["pre"].astype(float).values
    post_a = df["post"].astype(float).values
    n = len(pre_a)
    if n < 2:
        return {"Metric": label, "N": n, "note": "insufficient data"}
    t, p = stats.ttest_rel(pre_a, post_a)
    d = cohens_d(pre_a, post_a)
    sig = "*" if p < 0.05 else ""
    return {
        "Metric": label,
        "Baseline M (SD)": f"{pre_a.mean():.1f} ({pre_a.std(ddof=1):.1f})",
        "Post M (SD)": f"{post_a.mean():.1f} ({post_a.std(ddof=1):.1f})",
        "p-value": f"{p:.3f}{sig}",
        "Cohen's d": f"{d:.2f}",
        "N": n,
    }


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV
    if not path.exists():
        print(f"Missing {path}. Run seed_study_data.py first.")
        sys.exit(1)

    df = pd.read_csv(path)
    print(f"\nTable 4.1 — Pre- and Post-Intervention Scores (N = {len(df)})\n")

    rows = [
        paired_row("Task Completion Rate (%)", df.get("pre_tcr"), df.get("post_tcr")),
        paired_row("NASA-TLX Composite", df["pre_nasa_tlx"], df["post_nasa_tlx"]),
        paired_row("PSQI Global Score", df["pre_psqi"], df["post_psqi"]),
        paired_row("Pure Procrastination Scale", df["pre_pps"], df["post_pps"]),
        paired_row("PSS-10 Score", df["pre_pss10"], df["post_pss10"]),
    ]

    table = pd.DataFrame(rows)
    cols = ["Metric", "Baseline M (SD)", "Post M (SD)", "p-value", "Cohen's d"]
    print(table[cols].to_string(index=False))
    print("\n* post_tcr aligned to seeded behavioral TCR after seed_study_data.py runs.\n")

    out = ROOT / "table41_survey.csv"
    table[cols].to_csv(out, index=False)
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
