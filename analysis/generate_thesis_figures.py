#!/usr/bin/env python3
"""
Generate publication-ready thesis figures from baseline_survey.csv + table41_survey.csv.

Usage (repo root):
  pip install pandas matplotlib numpy scipy
  python analysis/generate_thesis_figures.py

Outputs in analysis/figures/:
  fig4_1_table41.png / .pdf          — Table 4.1 as figure
  fig4_2_pre_post_bars.png / .pdf    — Pre vs post bar chart (5 metrics)
  fig4_3_paired_spaghetti.png / .pdf — Individual participant trajectories
  fig4_4_behavioral_summary.png      — In-app behavioral proxies (optional CSV)
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)

SURVEY = ROOT / "baseline_survey.csv"
TABLE = ROOT / "table41_survey.csv"
BEHAVIORAL = ROOT / "freeside_behavioral_2026-06-07_2026-06-28_n12.csv"

METRICS = [
    {
        "key": "tcr",
        "pre": "pre_tcr",
        "post": "post_tcr",
        "label": "Task Completion\nRate (%)",
        "short": "TCR",
        "color": "#4648d4",
        "higher_better": True,
    },
    {
        "key": "nasa",
        "pre": "pre_nasa_tlx",
        "post": "post_nasa_tlx",
        "label": "NASA-TLX\nComposite",
        "short": "NASA-TLX",
        "color": "#7c3aed",
        "higher_better": False,
    },
    {
        "key": "psqi",
        "pre": "pre_psqi",
        "post": "post_psqi",
        "label": "PSQI\nGlobal Score",
        "short": "PSQI",
        "color": "#0891b2",
        "higher_better": False,
    },
    {
        "key": "pps",
        "pre": "pre_pps",
        "post": "post_pps",
        "label": "Pure Procrastination\nScale (PPS)",
        "short": "PPS",
        "color": "#d97706",
        "higher_better": False,
    },
    {
        "key": "pss",
        "pre": "pre_pss10",
        "post": "post_pss10",
        "label": "PSS-10\nStress Score",
        "short": "PSS-10",
        "color": "#dc2626",
        "higher_better": False,
    },
]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


def cohens_d(pre: np.ndarray, post: np.ndarray, higher_better: bool) -> float:
    diff = (post - pre) if higher_better else (pre - post)
    sd = np.std(pre, ddof=1)
    return float(np.mean(diff) / sd) if sd > 0 else 0.0


def paired_stats(df: pd.DataFrame, pre_col: str, post_col: str, higher_better: bool) -> dict:
    sub = df[[pre_col, post_col]].dropna().astype(float)
    pre = sub[pre_col].values
    post = sub[post_col].values
    t, p = stats.ttest_rel(pre, post)
    d = cohens_d(pre, post, higher_better)
    return {
        "n": len(pre),
        "pre_m": pre.mean(),
        "pre_sd": pre.std(ddof=1),
        "post_m": post.mean(),
        "post_sd": post.std(ddof=1),
        "p": p,
        "d": d,
    }


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(OUT / f"{name}.png")
    fig.savefig(OUT / f"{name}.pdf")
    print(f"  saved {name}.png + .pdf")


def fig_table41(table_df: pd.DataFrame, n: int) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.axis("off")
    ax.set_title(
        f"Table 4.1 — Pre- and Post-Intervention Scores (N = {n})",
        fontsize=12,
        fontweight="bold",
        pad=16,
    )

    cols = ["Metric", "Baseline M (SD)", "Post M (SD)", "p-value", "Cohen's d"]
    cell_text = table_df[cols].values.tolist()

    table = ax.table(
        cellText=cell_text,
        colLabels=cols,
        loc="center",
        cellLoc="center",
        colColours=["#eef0ff"] * len(cols),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.8)

    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(fontweight="bold")
        if col == 0 and row > 0:
            cell.set_text_props(ha="left")
            cell.PAD = 0.08

    fig.text(
        0.5, 0.02,
        "Note: * p < .05, two-tailed paired-samples t-test. "
        "For TCR, higher post scores indicate improvement; "
        "for all other measures, lower post scores indicate improvement.",
        ha="center",
        fontsize=8,
        color="#555",
    )
    save(fig, "fig4_1_table41")
    plt.close(fig)


def fig_pre_post_bars(df: pd.DataFrame, n: int) -> None:
    fig, axes = plt.subplots(1, 5, figsize=(14, 4.5))
    fig.suptitle(
        f"Figure 4.2 — Pre- vs Post-Intervention Comparison (N = {n})",
        fontsize=13,
        fontweight="bold",
        y=1.02,
    )

    for ax, m in zip(axes, METRICS):
        st = paired_stats(df, m["pre"], m["post"], m["higher_better"])
        means = [st["pre_m"], st["post_m"]]
        sems = [st["pre_sd"] / np.sqrt(st["n"]), st["post_sd"] / np.sqrt(st["n"])]

        ax.bar(
            [0, 1], means,
            color=[m["color"] + "55", m["color"]],
            edgecolor=m["color"],
            linewidth=1.5,
            width=0.55,
            zorder=3,
        )
        ax.errorbar([0, 1], means, yerr=sems, fmt="none", color="#333", capsize=4, linewidth=1.2)

        sub = df[[m["pre"], m["post"]]].dropna()
        for _, row in sub.iterrows():
            ax.plot([0, 1], [row[m["pre"]], row[m["post"]]],
                    color=m["color"], alpha=0.22, linewidth=0.9, zorder=2)

        p_str = f"p = {st['p']:.3f}" + (" *" if st["p"] < 0.05 else "")
        d_str = f"d = {st['d']:.2f}"
        ax.set_title(f"{p_str}\n{d_str}", fontsize=8.5, color="#444")

        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Baseline", "Post"])
        ax.set_xlabel(m["label"], fontsize=9, fontweight="semibold")
        ax.set_ylabel("Mean score")

        if m["higher_better"]:
            ax.annotate("↑ better", xy=(0.98, 0.04), xycoords="axes fraction",
                        ha="right", fontsize=7, color="#2d7a3a")
        else:
            ax.annotate("↓ better", xy=(0.98, 0.96), xycoords="axes fraction",
                        ha="right", va="top", fontsize=7, color="#2d7a3a")

    pre_patch = mpatches.Patch(facecolor="#99999955", edgecolor="#666", label="Baseline")
    post_patch = mpatches.Patch(facecolor="#4648d4", edgecolor="#4648d4", label="Post")
    fig.legend(handles=[pre_patch, post_patch], loc="lower center", ncol=2,
               bbox_to_anchor=(0.5, -0.06), frameon=False)

    save(fig, "fig4_2_pre_post_bars")
    plt.close(fig)


def fig_paired_change(df: pd.DataFrame, n: int) -> None:
    """Horizontal dumbbell chart — effect direction at a glance."""
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = []
    pre_vals = []
    post_vals = []
    colors = []

    for m in METRICS:
        st = paired_stats(df, m["pre"], m["post"], m["higher_better"])
        labels.append(m["short"])
        pre_vals.append(st["pre_m"])
        post_vals.append(st["post_m"])
        colors.append(m["color"])

    y = np.arange(len(labels))
    for i, (pre, post, c, m) in enumerate(zip(pre_vals, post_vals, colors, METRICS)):
        ax.plot([pre, post], [i, i], color=c, linewidth=2.5, alpha=0.5, zorder=2)
        ax.scatter(pre, i, color=c, s=80, edgecolors="white", linewidths=1.2, zorder=3, label="Baseline")
        ax.scatter(post, i, color=c, s=80, marker="D", edgecolors="white", linewidths=1.2, zorder=3)

        delta = post - pre
        if not m["higher_better"]:
            delta = -delta
        sign = "+" if delta > 0 else ""
        ax.text(max(pre, post) + 1.5, i, f"{sign}{delta:.1f}", va="center", fontsize=8, color="#444")

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Mean score")
    ax.set_title(
        f"Figure 4.3 — Mean Change by Metric (N = {n})\n"
        "Circles = baseline · Diamonds = post · Numbers = improvement magnitude",
        fontsize=11,
        fontweight="bold",
    )
    ax.invert_yaxis()
    save(fig, "fig4_3_paired_change")
    plt.close(fig)


def _single_pre_post_panel(ax, df: pd.DataFrame, pre_col: str, post_col: str,
                           label: str, color: str, higher_better: bool, ylabel: str) -> dict:
    st = paired_stats(df, pre_col, post_col, higher_better)
    means = [st["pre_m"], st["post_m"]]
    sems = [st["pre_sd"] / np.sqrt(st["n"]), st["post_sd"] / np.sqrt(st["n"])]
    ax.bar([0, 1], means, color=[color + "55", color], edgecolor=color, linewidth=1.5, width=0.5, zorder=3)
    ax.errorbar([0, 1], means, yerr=sems, fmt="none", color="#333", capsize=4, linewidth=1.2)
    sub = df[[pre_col, post_col]].dropna()
    for _, row in sub.iterrows():
        ax.plot([0, 1], [row[pre_col], row[post_col]], color=color, alpha=0.25, linewidth=0.9, zorder=2)
    p_str = f"p = {st['p']:.3f}" + (" *" if st["p"] < 0.05 else "")
    ax.set_title(f"{label}\n{p_str}, d = {st['d']:.2f}", fontsize=9, fontweight="bold")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Baseline", "Post"])
    ax.set_ylabel(ylabel)
    return st


def fig_rq3_sleep(survey_df: pd.DataFrame, behavioral_path: Path, n: int) -> None:
    """§4.4 — PSQI (survey) + SQDS proxy (sleep logs)."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    fig.suptitle(f"Figure 4.4 — Sleep Quality (RQ3) · N = {n}", fontsize=12, fontweight="bold", y=1.02)

    _single_pre_post_panel(
        axes[0], survey_df, "pre_psqi", "post_psqi",
        "PSQI Global Score (survey)", "#0891b2", False,
        "Score (lower = better sleep)",
    )

    if behavioral_path.exists():
        merged = survey_df.merge(pd.read_csv(behavioral_path), on="user_id", how="inner")
        x = np.arange(len(merged))
        w = 0.35
        hours = merged["avg_hours_slept"].fillna(0)
        rested = merged["avg_rested_score"].fillna(0)
        ax = axes[1]
        ax.bar(x - w / 2, hours, w, label="Avg hours slept", color="#0891b2", alpha=0.85)
        ax2 = ax.twinx()
        ax2.bar(x + w / 2, rested, w, label="Avg rested (1–5)", color="#06b6d4", alpha=0.85)
        ax.axhline(hours.mean(), color="#0891b2", linestyle="--", linewidth=1, alpha=0.7)
        ax2.axhline(rested.mean(), color="#06b6d4", linestyle="--", linewidth=1, alpha=0.7)
        ax.set_xlabel("Participant")
        ax.set_ylabel("Hours slept")
        ax2.set_ylabel("Rested score (1–5)")
        ax.set_title(
            f"SQDS Proxy (in-app sleep pulse)\n"
            f"M = {hours.mean():.1f} h · rested = {rested.mean():.1f}/5",
            fontsize=9, fontweight="bold",
        )
        ax.set_xticks(x)
        ax.set_xticklabels([f"P{i+1:02d}" for i in range(len(merged))], fontsize=7)
        lines1, lab1 = ax.get_legend_handles_labels()
        lines2, lab2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, lab1 + lab2, loc="upper right", fontsize=7)
        ax2.spines["top"].set_visible(False)

    save(fig, "fig4_4_rq3_sleep")
    plt.close(fig)


def fig_rq4_procrastination(survey_df: pd.DataFrame, behavioral_path: Path, n: int) -> None:
    """§4.5 — PPS (survey) + PFI proxy (delay + breakdowns)."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    fig.suptitle(f"Figure 4.5 — Procrastination Frequency (RQ4) · N = {n}", fontsize=12, fontweight="bold", y=1.02)

    _single_pre_post_panel(
        axes[0], survey_df, "pre_pps", "post_pps",
        "Pure Procrastination Scale (PPS)", "#d97706", False,
        "Score (lower = less procrastination)",
    )

    if behavioral_path.exists():
        merged = survey_df.merge(pd.read_csv(behavioral_path), on="user_id", how="inner")
        x = np.arange(len(merged))
        delay_h = merged["avg_initiation_delay_minutes"].fillna(0) / 60
        breaks = merged["total_breakdowns_requested"].fillna(0)
        ax = axes[1]
        ax.bar(x - 0.2, delay_h, 0.4, label="Initiation delay (h)", color="#d97706", alpha=0.85)
        ax2 = ax.twinx()
        ax2.bar(x + 0.2, breaks, 0.4, label="Co-Pilot breakdowns", color="#f59e0b", alpha=0.85)
        ax.axhline(delay_h.mean(), color="#d97706", linestyle="--", linewidth=1, alpha=0.7)
        ax2.axhline(breaks.mean(), color="#f59e0b", linestyle="--", linewidth=1, alpha=0.7)
        ax.set_xlabel("Participant")
        ax.set_ylabel("Hours (task create → first action)")
        ax2.set_ylabel("Breakdown requests")
        ax.set_title(
            f"PFI Proxy (behavioral logs)\n"
            f"M delay = {delay_h.mean():.1f} h · M breakdowns = {breaks.mean():.1f}",
            fontsize=9, fontweight="bold",
        )
        ax.set_xticks(x)
        ax.set_xticklabels([f"P{i+1:02d}" for i in range(len(merged))], fontsize=7)
        lines1, lab1 = ax.get_legend_handles_labels()
        lines2, lab2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, lab1 + lab2, loc="upper right", fontsize=7)
        ax2.spines["top"].set_visible(False)

    save(fig, "fig4_5_rq4_procrastination")
    plt.close(fig)


def fig_rq5_stress(survey_df: pd.DataFrame, behavioral_path: Path, n: int) -> None:
    """§4.6 — PSS-10 (survey) + SWBBS proxy (energy + burnout flags)."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    fig.suptitle(f"Figure 4.6 — Perceived Stress & Burnout Risk (RQ5) · N = {n}", fontsize=12, fontweight="bold", y=1.02)

    _single_pre_post_panel(
        axes[0], survey_df, "pre_pss10", "post_pss10",
        "PSS-10 (Perceived Stress)", "#dc2626", False,
        "Score (lower = less stress)",
    )

    if behavioral_path.exists():
        merged = survey_df.merge(pd.read_csv(behavioral_path), on="user_id", how="inner")
        x = np.arange(len(merged))
        energy = merged["overall_avg_energy"].fillna(0)
        ax = axes[1]
        colors = ["#dc2626" if bf else "#4648d4" for bf in merged["burnout_flag"].fillna(False)]
        ax.bar(x, energy, color=colors, alpha=0.85, edgecolor="white")
        ax.axhline(energy.mean(), color="#333", linestyle="--", linewidth=1,
                   label=f"M = {energy.mean():.1f}/10")
        for i, (_, row) in enumerate(merged.iterrows()):
            if row.get("burnout_flag"):
                ax.annotate("⚠", (i, row["overall_avg_energy"]), ha="center", va="bottom", fontsize=10)
        ax.set_xlabel("Participant")
        ax.set_ylabel("Mean daily energy (1–10)")
        ax.set_title("SWBBS Proxy — energy & burnout signal", fontsize=9, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels([f"P{i+1:02d}" for i in range(len(merged))], fontsize=7)
        ax.set_ylim(0, 10.5)
        warn = mpatches.Patch(facecolor="#dc2626", label="Burnout flag (3+ declining days)")
        ok = mpatches.Patch(facecolor="#4648d4", label="Stable trajectory")
        ax.legend(handles=[ok, warn, ax.lines[0] if ax.lines else mpatches.Patch()], fontsize=7)

    save(fig, "fig4_6_rq5_stress")
    plt.close(fig)


def fig_behavioral_overview(behavioral_path: Path, survey_df: pd.DataFrame) -> None:
    if not behavioral_path.exists():
        return
    bdf = pd.read_csv(behavioral_path)
    merged = survey_df.merge(bdf, on="user_id", how="inner")
    if merged.empty:
        return

    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    fig.suptitle(
        "Figure 4.7 — Behavioral Overview (all in-app proxies)",
        fontsize=12,
        fontweight="bold",
    )

    panels = [
        ("tcr_percentage", "Task Completion Rate (%)", "#4648d4", None),
        ("reroute_percentage", "CLCS Reroute Rate (%)", "#7c3aed", None),
        ("total_breakdowns_requested", "Co-Pilot Breakdowns (count)", "#d97706", None),
        ("overall_avg_energy", "Mean Daily Energy (1–10)", "#dc2626", None),
    ]

    for ax, (col, title, color, _) in zip(axes.flat, panels):
        vals = merged[col].dropna()
        if vals.empty:
            ax.set_visible(False)
            continue
        ax.bar(range(len(vals)), vals.values, color=color + "99", edgecolor=color)
        ax.axhline(vals.mean(), color="#333", linestyle="--", linewidth=1, label=f"M = {vals.mean():.1f}")
        ax.set_title(title, fontsize=10, fontweight="semibold")
        ax.set_xlabel("Participant")
        ax.set_ylabel("Value")
        ax.legend(fontsize=8)

    save(fig, "fig4_7_behavioral_overview")
    plt.close(fig)


def main() -> None:
    if not SURVEY.exists():
        raise SystemExit(f"Missing {SURVEY}")

    df = pd.read_csv(SURVEY)
    n = len(df)

    if TABLE.exists():
        table_df = pd.read_csv(TABLE)
    else:
        rows = []
        for m in METRICS:
            st = paired_stats(df, m["pre"], m["post"], m["higher_better"])
            sig = "*" if st["p"] < 0.05 else ""
            rows.append({
                "Metric": m["short"] if m["key"] != "tcr" else "Task Completion Rate (%)",
                "Baseline M (SD)": f"{st['pre_m']:.1f} ({st['pre_sd']:.1f})",
                "Post M (SD)": f"{st['post_m']:.1f} ({st['post_sd']:.1f})",
                "p-value": f"{st['p']:.3f}{sig}",
                "Cohen's d": f"{st['d']:.2f}",
            })
        table_df = pd.DataFrame(rows)

    print(f"Generating thesis figures for N = {n} → {OUT}/")
    fig_table41(table_df, n)
    fig_pre_post_bars(df, n)
    fig_paired_change(df, n)
    fig_rq3_sleep(df, BEHAVIORAL, n)
    fig_rq4_procrastination(df, BEHAVIORAL, n)
    fig_rq5_stress(df, BEHAVIORAL, n)
    fig_behavioral_overview(BEHAVIORAL, df)
    print("\nDone. Insert PNG or PDF from analysis/figures/ into your thesis Word doc.")


if __name__ == "__main__":
    main()
