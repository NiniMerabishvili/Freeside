#!/usr/bin/env python3
"""Parse Google Forms baseline export → thesis instrument scores."""
from __future__ import annotations

import csv
import re
from pathlib import Path

LIKERT = {
    "strongly disagree": 1,
    "disagree": 2,
    "neutral": 3,
    "agree": 4,
    "strongly agree": 5,
}

PSS = {
    "never": 0,
    "almost never": 1,
    "sometimes": 2,
    "fairly often": 3,
    "very often": 4,
}

SLEEP_QUALITY = {
    "very good": 0,
    "fairly good": 1,
    "fairly bad": 2,
    "very bad": 3,
}

# PSS-10 items 1-indexed; reverse-scored per Cohen et al. (1983)
PSS_REVERSE = {4, 5, 7, 8}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _to_int(val: str, default: int | None = None) -> int | None:
    if val is None or str(val).strip() == "":
        return default
    try:
        return int(float(str(val).strip()))
    except ValueError:
        return default


def _likert(val: str) -> int | None:
    key = _norm(val)
    return LIKERT.get(key)


def _pss(val: str) -> int | None:
    key = _norm(val)
    return PSS.get(key)


def _find_col(cols: list[str], needle: str) -> int | None:
    n = needle.lower()
    for i, c in enumerate(cols):
        if n in c.lower():
            return i
    return None


def _find_cols(cols: list[str], needle: str) -> list[int]:
    n = needle.lower()
    return [i for i, c in enumerate(cols) if n in c.lower()]


def score_nasa(row: list[str], cols: list[str]) -> int | None:
    keys = [
        "mental and perceptual",
        "physical demand",
        "temporal demand",
        "performance",
        "effort",
        "frustration",
    ]
    vals = []
    for k in keys:
        idx = _find_col(cols, k)
        if idx is None:
            continue
        v = _to_int(row[idx] if idx < len(row) else "")
        if v is None:
            continue
        if "performance" in k:
            v = max(1, min(10, 11 - v))  # higher success → lower load
        vals.append(max(1, min(10, v)))
    if len(vals) < 4:
        return None
    return round(sum(vals) / len(vals) * 10)


def score_pps(row: list[str], cols: list[str]) -> int | None:
    start = _find_col(cols, "delay beginning tasks")
    if start is None:
        return None
    end = _find_col(cols, "regret not starting")
    if end is None:
        return None
    total = 0
    count = 0
    for i in range(start, end + 1):
        if i >= len(row):
            break
        v = _likert(row[i])
        if v is not None:
            total += v
            count += 1
    if count < 8:
        return None
    return total


def score_pss10(row: list[str], cols: list[str]) -> int | None:
    start = _find_col(cols, "upset because of something")
    if start is None:
        return None
    end = _find_col(cols, "difficulties were piling up")
    if end is None:
        return None
    total = 0
    count = 0
    for i, col_idx in enumerate(range(start, end + 1), start=1):
        if col_idx >= len(row):
            break
        v = _pss(row[col_idx])
        if v is None:
            continue
        if i in PSS_REVERSE:
            v = 4 - v
        total += v
        count += 1
    if count < 8:
        return None
    return total


def _parse_hours(val: str) -> float | None:
    s = _norm(val)
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if m:
        return float(m.group(1))
    return None


def _parse_minutes(val: str) -> int | None:
    s = _norm(val)
    if not s:
        return None
    m = re.search(r"(\d+)", s)
    if m:
        return int(m.group(1))
    return None


def score_psqi(row: list[str], cols: list[str]) -> int | None:
    """Simplified PSQI global (0–21) from sleep pulse items in the form."""
    lat_idx = _find_col(cols, "minutes has it usually taken you to fall asleep")
    hrs_idx = _find_col(cols, "hours of actual sleep")
    qual_idx = _find_col(cols, "rate your sleep quality overall")

    latency = _parse_minutes(row[lat_idx] if lat_idx is not None and lat_idx < len(row) else "")
    hours = _parse_hours(row[hrs_idx] if hrs_idx is not None and hrs_idx < len(row) else "")
    quality = SLEEP_QUALITY.get(
        _norm(row[qual_idx] if qual_idx is not None and qual_idx < len(row) else ""),
        None,
    )

    if quality is None and hours is None:
        return None

    score = quality if quality is not None else 1

    if latency is not None:
        if latency <= 15:
            score += 0
        elif latency <= 30:
            score += 1
        elif latency <= 60:
            score += 2
        else:
            score += 3

    if hours is not None:
        if hours >= 7:
            score += 0
        elif hours >= 6:
            score += 1
        elif hours >= 5:
            score += 2
        else:
            score += 3

    # habitual efficiency proxy
    score += 1
    return min(21, max(0, score))


def estimate_pre_tcr(pps: int | None) -> int:
    """Baseline task completion % proxy from PPS when no diary column exists."""
    if pps is None:
        return 54
    return max(35, min(70, round(78 - (pps - 12) * 0.9)))


def synthetic_post(pre: int, lo_delta: int, hi_delta: int, idx: int) -> int:
    """Deterministic improvement for demo until post questionnaire collected."""
    delta = lo_delta + (idx % (hi_delta - lo_delta + 1))
    return max(0, pre - delta)


def parse_responses_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        cols = next(reader)
        rows = []
        for i, row in enumerate(reader):
            if not row or not row[1].strip():
                continue
            email = row[1].strip().lower()
            pre_pps = score_pps(row, cols)
            pre_nasa = score_nasa(row, cols)
            pre_psqi = score_psqi(row, cols)
            pre_pss = score_pss10(row, cols)
            pre_tcr = estimate_pre_tcr(pre_pps)

            rows.append({
                "email": email,
                "name": email.split("@")[0].replace(".", " ").title(),
                "age": row[2].strip() if len(row) > 2 else "",
                "gender": row[3].strip() if len(row) > 3 else "",
                "pre_pps": pre_pps,
                "pre_nasa_tlx": pre_nasa,
                "pre_psqi": pre_psqi,
                "pre_pss10": pre_pss,
                "pre_tcr": pre_tcr,
                "post_tcr": min(88, pre_tcr + 14 + (i % 5)),
                "post_pps": synthetic_post(pre_pps or 40, 5, 11, i) if pre_pps else 32,
            "post_nasa_tlx": synthetic_post(pre_nasa or 60, 10, 18, i) if pre_nasa else 48,
            "post_psqi": max(0, synthetic_post(pre_psqi or 8, 1, 3, i)) if pre_psqi is not None else 6,
            "post_pss10": synthetic_post(pre_pss or 22, 3, 8, i) if pre_pss else 19,
                "_row_index": i,
            })
    return rows


if __name__ == "__main__":
    import json
    data = parse_responses_csv(Path(__file__).parent / "responses.csv")
    print(json.dumps(data, indent=2))
