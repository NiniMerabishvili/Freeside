"""
Behavioral metrics service — computes in-app proxy metrics for thesis analysis.

Each function accepts (user_id, start_date, end_date) and returns a typed dict
ready for export to CSV / paired t-test pipeline.
"""
import csv
import io
from collections import defaultdict
from datetime import date, datetime, timezone
from supabase import Client


# ---------------------------------------------------------------------------
# Metric 1 — Task Completion Rate (TCR)
# Proxy for: PPS (Pure Procrastination Scale) and NASA-TLX (Performance subscale)
# ---------------------------------------------------------------------------

def get_task_completion_rate(
    db: Client,
    user_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Ratio of completed tasks to tasks created within the study window.

    Returns
    -------
    {
        metric          : 'TCR',
        user_id         : str,
        total_created   : int,
        total_completed : int,
        tcr_percentage  : float   # 0.0 – 100.0; 0.0 when no tasks created
    }
    """
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()

    # Total tasks created in window
    created_resp = (
        db.table("tasks")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .gte("created_at", start_iso)
        .lte("created_at", end_iso)
        .execute()
    )
    total_created: int = created_resp.count or 0

    # Tasks completed in window (completed_at is NOT NULL and within range)
    completed_resp = (
        db.table("session_logs")
        .select("task_id", count="exact")
        .eq("user_id", user_id)
        .not_.is_("completed_at", "null")
        .gte("completed_at", start_iso)
        .lte("completed_at", end_iso)
        .execute()
    )
    total_completed: int = completed_resp.count or 0

    tcr_percentage = (
        round((total_completed / total_created) * 100, 2)
        if total_created > 0
        else 0.0
    )

    return {
        "metric": "TCR",
        "user_id": user_id,
        "total_created": total_created,
        "total_completed": total_completed,
        "tcr_percentage": tcr_percentage,
    }


# ---------------------------------------------------------------------------
# Metric 2 — Cognitive Load Index proxy (CLI_Proxy)
# Proxy for: NASA-TLX (Mental Demand + Frustration subscales)
# ---------------------------------------------------------------------------

def get_cognitive_load_index(
    db: Client,
    user_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Rerouting rate within the study window as a behavioral proxy for cognitive load.
    A high rerouting rate — particularly on low-energy days — indicates the system
    is actively redistributing cognitive demand on behalf of the user.

    Returns
    -------
    {
        metric              : 'CLI_Proxy',
        user_id             : str,
        total_interactions  : int,
        reroute_count       : int,
        reroute_percentage  : float   # 0.0 – 100.0; 0.0 when no interactions
    }
    """
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()

    # All task interactions in window — use created_at as the interaction timestamp
    # (started_at may be null for sessions logged only at completion)
    total_resp = (
        db.table("session_logs")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .gte("completed_at", start_iso)
        .lte("completed_at", end_iso)
        .execute()
    )
    total_interactions: int = total_resp.count or 0

    # Subset where the system rerouted the task
    rerouted_resp = (
        db.table("session_logs")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("was_rerouted", True)
        .gte("completed_at", start_iso)
        .lte("completed_at", end_iso)
        .execute()
    )
    reroute_count: int = rerouted_resp.count or 0

    reroute_percentage = (
        round((reroute_count / total_interactions) * 100, 2)
        if total_interactions > 0
        else 0.0
    )

    return {
        "metric": "CLI_Proxy",
        "user_id": user_id,
        "total_interactions": total_interactions,
        "reroute_count": reroute_count,
        "reroute_percentage": reroute_percentage,
    }


# ---------------------------------------------------------------------------
# Metric 3 — Sleep Quality & Duration Score proxy (SQDS_Proxy)
# Proxy for: PSQI (Pittsburgh Sleep Quality Index)
# Causal chain (thesis argument): better task management → lower work-related
# rumination (Berset et al., 2011) → better sleep quality.
# ---------------------------------------------------------------------------

def get_sleep_quality_score(
    db: Client,
    user_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Mean hours slept and mean subjective restedness within the study window,
    derived from daily in-app sleep pulse checks.

    Returns None for avg fields — not 0 — when no logs exist, so that missing
    data is distinguishable from a genuine zero in the paired t-test pipeline.
    A zero would artificially suppress the participant mean and skew group
    statistics; None signals the analyst to exclude this participant from the
    SQDS analysis rather than impute.

    Returns
    -------
    {
        metric           : 'SQDS_Proxy',
        user_id          : str,
        avg_hours_slept  : float | None,   # mean across logs_count entries
        avg_rested_score : float | None,   # mean of 1–5 subjective rating
        logs_count       : int             # 0 when no data
    }
    """
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()

    try:
        resp = (
            db.table("sleep_logs")
            .select("hours_slept, rested_score")
            .eq("user_id", user_id)
            .gte("logged_at", start_iso)
            .lte("logged_at", end_iso)
            .execute()
        )
        rows: list[dict] = resp.data or []
    except Exception:
        # sleep_logs table may not exist yet — return null values rather than crash
        rows = []
    logs_count = len(rows)

    if logs_count == 0:
        return {
            "metric": "SQDS_Proxy",
            "user_id": user_id,
            "avg_hours_slept": None,
            "avg_rested_score": None,
            "logs_count": 0,
        }

    avg_hours_slept = round(
        sum(r["hours_slept"] for r in rows) / logs_count, 2
    )
    avg_rested_score = round(
        sum(r["rested_score"] for r in rows) / logs_count, 2
    )

    return {
        "metric": "SQDS_Proxy",
        "user_id": user_id,
        "avg_hours_slept": avg_hours_slept,
        "avg_rested_score": avg_rested_score,
        "logs_count": logs_count,
    }


# ---------------------------------------------------------------------------
# Metric 4 — Procrastination Frequency Index proxy (PFI_Proxy)
# Proxy for: PPS / IPS (Pure Procrastination Scale / Irrational Procrastination Scale)
# Grounding: Steel (2007) Temporal Motivation Theory — motivation collapses
# as perceived delay grows. Two behavioral signals capture this:
#   (a) how long before the user first touches a task after creating it, and
#   (b) how often they invoke AI breakdown help as an avoidance-lowering tool.
# ---------------------------------------------------------------------------

def get_procrastination_frequency_index(
    db: Client,
    user_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Behavioral proxy for procrastination derived from task initiation delay
    and AI co-pilot breakdown request frequency.

    Initiation delay logic
    ----------------------
    For every task created within the window, we find its *first* view event
    in session_logs (MIN viewed_at per task_id). Only the first view is used
    because repeat views would compress the measured delay and undercount
    avoidance. Tasks that were never viewed are included with a delay equal to
    the full window length — they represent maximum avoidance and excluding
    them would optimistically bias the mean.

    Breakdown frequency logic
    -------------------------
    Each 'break_down' event in copilot_logs is a direct behavioral
    operationalization of Steel's (2007) expectancy mechanism: the user
    perceives a task as too large (low expectancy) and requests decomposition
    to lower the activation threshold. Higher frequency = more procrastination
    events intercepted by Freeside.

    Returns
    -------
    {
        metric                      : 'PFI_Proxy',
        user_id                     : str,
        avg_initiation_delay_minutes: float | None,  # None if no tasks created
        tasks_evaluated             : int,
        tasks_never_viewed          : int,
        total_breakdowns_requested  : int
    }
    """
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()

    # --- (a) Initiation delay --------------------------------------------------

    # All tasks created by this user in the window
    tasks_resp = (
        db.table("tasks")
        .select("id, created_at")
        .eq("user_id", user_id)
        .gte("created_at", start_iso)
        .lte("created_at", end_iso)
        .execute()
    )
    tasks: list[dict] = tasks_resp.data or []

    if not tasks:
        avg_initiation_delay_minutes = None
        tasks_evaluated = 0
        tasks_never_viewed = 0
    else:
        task_ids = [t["id"] for t in tasks]
        task_created_map: dict[str, str] = {t["id"]: t["created_at"] for t in tasks}

        # First start per task — fetch all session rows for these task ids
        # Uses started_at; falls back to completed_at if started_at is null
        views_resp = (
            db.table("session_logs")
            .select("task_id, started_at, completed_at")
            .eq("user_id", user_id)
            .in_("task_id", task_ids)
            .execute()
        )
        view_rows: list[dict] = views_resp.data or []

        # Build a map of task_id → earliest interaction timestamp
        first_view: dict[str, str] = {}
        for row in view_rows:
            tid = row["task_id"]
            ts = row.get("started_at") or row.get("completed_at")
            if not ts:
                continue
            if tid not in first_view or ts < first_view[tid]:
                first_view[tid] = ts

        # Window end acts as the ceiling for never-started tasks
        window_end_iso = f"{end_iso}T23:59:59+00:00"

        delays_minutes: list[float] = []
        tasks_never_viewed = 0

        for task in tasks:
            tid = task["id"]
            created_raw = task["created_at"]
            viewed_raw = first_view.get(tid, window_end_iso)

            if tid not in first_view:
                tasks_never_viewed += 1

            created_dt = datetime.fromisoformat(created_raw)
            viewed_dt = datetime.fromisoformat(viewed_raw)

            # Normalise to UTC if naive (Supabase returns timezone-aware strings)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            if viewed_dt.tzinfo is None:
                viewed_dt = viewed_dt.replace(tzinfo=timezone.utc)

            delay = (viewed_dt - created_dt).total_seconds() / 60
            delays_minutes.append(max(delay, 0.0))  # guard against clock skew

        tasks_evaluated = len(tasks)
        avg_initiation_delay_minutes = (
            round(sum(delays_minutes) / tasks_evaluated, 2)
            if tasks_evaluated > 0
            else None
        )

    # --- (b) Breakdown frequency ----------------------------------------------

    breakdowns_resp = (
        db.table("copilot_logs")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("message_type", "break_down")
        .gte("created_at", start_iso)
        .lte("created_at", end_iso)
        .execute()
    )
    total_breakdowns_requested: int = breakdowns_resp.count or 0

    return {
        "metric": "PFI_Proxy",
        "user_id": user_id,
        "avg_initiation_delay_minutes": avg_initiation_delay_minutes,
        "tasks_evaluated": tasks_evaluated,
        "tasks_never_viewed": tasks_never_viewed,
        "total_breakdowns_requested": total_breakdowns_requested,
    }


# ---------------------------------------------------------------------------
# Metric 5 — Subjective Well-Being & Burnout Risk Score proxy (SWBBS_Proxy)
# Proxy for: PSS-10 (Perceived Stress Scale) + OLBI (Oldenburg Burnout Inventory)
# Grounding: Bakker & Demerouti (2007) Job Demands-Resources model — burnout
# occurs when demands chronically exceed resources. Freeside's energy score is
# the in-app operationalization of "available resources." A multi-day declining
# trend signals resource depletion before the participant consciously notices it
# (Van Dongen et al., 2003 demonstrated the same blindspot for sleep debt).
# ---------------------------------------------------------------------------

def get_wellbeing_burnout_score(
    db: Client,
    user_id: str,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Rolling energy trend analysis as a behavioral early-warning proxy for
    burnout, correlated against PSS-10 and OLBI in the paired t-test pipeline.

    Burnout flag logic
    ------------------
    We examine the TAIL of the chronologically sorted daily averages. Starting
    from the most recent day and walking backwards, we count how many
    consecutive days show a strict decrease (each day strictly lower than the
    previous). If the streak is >= 3, burnout_flag is True.

    Using the tail — not any 3-day window in the series — is intentional: a
    recovering participant might have had a bad patch mid-study but stabilised.
    The flag captures the participant's *current* trajectory, which is the
    clinically relevant signal for an intervention.

    Rolling 7-day average
    ---------------------
    Each entry in daily_trend_array includes a rolling_7day_avg field. This is
    what the thesis PDF recommends plotting alongside OLBI scores. Fewer than
    7 prior data points simply average what is available (expanding window).
    Days with no logs are omitted from the series rather than zero-filled, so
    the plot gaps are honest about missing data.

    Returns
    -------
    {
        metric            : 'SWBBS_Proxy',
        user_id           : str,
        overall_avg_energy: float | None,   # None if no logs in window
        burnout_flag      : bool,           # True = 3+ consecutive declining days at tail
        consecutive_decline_days: int,      # length of the trailing decline streak
        daily_trend_array : list[dict]      # [{date, avg_energy, rolling_7day_avg}, ...]
    }
    """
    start_iso = start_date.isoformat()
    end_iso = end_date.isoformat()

    resp = (
        db.table("energy_logs")
        .select("confirmed_score, logged_at")
        .eq("user_id", user_id)
        .gte("logged_at", start_iso)
        .lte("logged_at", end_iso)
        .execute()
    )
    rows: list[dict] = resp.data or []

    if not rows:
        return {
            "metric": "SWBBS_Proxy",
            "user_id": user_id,
            "overall_avg_energy": None,
            "burnout_flag": False,
            "consecutive_decline_days": 0,
            "daily_trend_array": [],
        }

    # --- Group scores by calendar date (user's local date via ISO prefix) ----
    scores_by_day: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        day_key = row["logged_at"][:10]  # "YYYY-MM-DD"
        scores_by_day[day_key].append(float(row["confirmed_score"]))

    # Sort days chronologically
    sorted_days = sorted(scores_by_day.keys())

    # --- Build daily averages -------------------------------------------------
    daily_avgs: list[float] = [
        round(sum(scores_by_day[d]) / len(scores_by_day[d]), 3)
        for d in sorted_days
    ]

    # --- Rolling 7-day average (expanding at the start) ----------------------
    def rolling_avg(values: list[float], idx: int, window: int = 7) -> float:
        start = max(0, idx - window + 1)
        chunk = values[start : idx + 1]
        return round(sum(chunk) / len(chunk), 3)

    daily_trend_array = [
        {
            "date": sorted_days[i],
            "avg_energy": daily_avgs[i],
            "rolling_7day_avg": rolling_avg(daily_avgs, i),
        }
        for i in range(len(sorted_days))
    ]

    # --- Overall mean ---------------------------------------------------------
    all_scores = [r["confirmed_score"] for r in rows]
    overall_avg_energy = round(sum(all_scores) / len(all_scores), 3)

    # --- Burnout flag: trailing strict-decrease streak of >= 3 days ----------
    consecutive_decline_days = 0
    if len(daily_avgs) >= 2:
        # Walk backwards from the last day
        for i in range(len(daily_avgs) - 1, 0, -1):
            if daily_avgs[i] < daily_avgs[i - 1]:
                consecutive_decline_days += 1
            else:
                break  # streak broken — stop counting

    burnout_flag = consecutive_decline_days >= 3

    return {
        "metric": "SWBBS_Proxy",
        "user_id": user_id,
        "overall_avg_energy": overall_avg_energy,
        "burnout_flag": burnout_flag,
        "consecutive_decline_days": consecutive_decline_days,
        "daily_trend_array": daily_trend_array,
    }


# ---------------------------------------------------------------------------
# Master Export — aggregates all 5 metrics across the study cohort
# ---------------------------------------------------------------------------

# Ordered columns for the wide-format export — matches the pandas merge key
# against the Google Forms baseline CSV (join on user_id).
EXPORT_COLUMNS = [
    "user_id",
    "tcr_percentage",
    "total_created",
    "total_completed",
    "reroute_percentage",
    "total_interactions",
    "reroute_count",
    "avg_hours_slept",
    "avg_rested_score",
    "sleep_logs_count",
    "avg_initiation_delay_minutes",
    "tasks_evaluated",
    "tasks_never_viewed",
    "total_breakdowns_requested",
    "overall_avg_energy",
    "consecutive_decline_days",
    "burnout_flag",
]


def export_thesis_data(
    db: Client,
    user_ids: list[str],
    start_date: date,
    end_date: date,
) -> dict:
    """
    Aggregate all 5 behavioral proxy metrics for every participant in the
    study cohort and return a structure immediately usable by pandas.

    Wide format — one row per participant — so the result merges directly
    against the Google Forms baseline CSV on the 'user_id' column:

        import pandas as pd
        behavioral = pd.DataFrame(result["rows"])
        survey     = pd.read_csv("baseline_survey.csv")
        merged     = survey.merge(behavioral, on="user_id", how="inner")

    The 'csv_string' field in the return value can be written straight to
    disk for archival or sent as a file download from the API endpoint.

    Parameters
    ----------
    db         : active Supabase Client (service role)
    user_ids   : list of participant user_ids (your N=10 cohort)
    start_date : study window start (inclusive)
    end_date   : study window end   (inclusive)

    Returns
    -------
    {
        rows       : list[dict]   # wide-format, one dict per participant
        columns    : list[str]    # column order matching EXPORT_COLUMNS
        csv_string : str          # UTF-8 CSV ready for pd.read_csv(StringIO(...))
        cohort_size: int          # len(user_ids)
        window     : { start, end }
    }
    """
    rows: list[dict] = []

    for uid in user_ids:
        tcr    = get_task_completion_rate(db, uid, start_date, end_date)
        cli    = get_cognitive_load_index(db, uid, start_date, end_date)
        sqds   = get_sleep_quality_score(db, uid, start_date, end_date)
        pfi    = get_procrastination_frequency_index(db, uid, start_date, end_date)
        swbbs  = get_wellbeing_burnout_score(db, uid, start_date, end_date)

        row: dict = {
            "user_id":                      uid,
            # TCR — proxy for PPS
            "tcr_percentage":               tcr["tcr_percentage"],
            "total_created":                tcr["total_created"],
            "total_completed":              tcr["total_completed"],
            # CLI — proxy for NASA-TLX
            "reroute_percentage":           cli["reroute_percentage"],
            "total_interactions":           cli["total_interactions"],
            "reroute_count":                cli["reroute_count"],
            # SQDS — proxy for PSQI
            "avg_hours_slept":              sqds["avg_hours_slept"],
            "avg_rested_score":             sqds["avg_rested_score"],
            "sleep_logs_count":             sqds["logs_count"],
            # PFI — proxy for PPS / IPS
            "avg_initiation_delay_minutes": pfi["avg_initiation_delay_minutes"],
            "tasks_evaluated":              pfi["tasks_evaluated"],
            "tasks_never_viewed":           pfi["tasks_never_viewed"],
            "total_breakdowns_requested":   pfi["total_breakdowns_requested"],
            # SWBBS — proxy for PSS-10 + OLBI
            "overall_avg_energy":           swbbs["overall_avg_energy"],
            "consecutive_decline_days":     swbbs["consecutive_decline_days"],
            "burnout_flag":                 swbbs["burnout_flag"],
        }

        rows.append(row)

    # Build CSV string (UTF-8, header row included)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    csv_string = buffer.getvalue()

    return {
        "rows": rows,
        "columns": EXPORT_COLUMNS,
        "csv_string": csv_string,
        "cohort_size": len(user_ids),
        "window": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
    }
