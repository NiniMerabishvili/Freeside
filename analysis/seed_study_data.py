#!/usr/bin/env python3
"""
One-shot study seed: parse Google Forms CSV → create Supabase auth users →
insert 3 weeks of behavioral logs (no participant login required).

Usage (from repo root, backend venv active):
  cd backend && source venv/bin/activate
  python ../analysis/seed_study_data.py

Requires backend/.env with SUPABASE_URL and SUPABASE_SERVICE_KEY.
"""
from __future__ import annotations

import json
import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))

from dotenv import load_dotenv
load_dotenv(ROOT / "backend" / ".env", override=True)

import os
from supabase import create_client

from parse_responses import parse_responses_csv

STUDY_START = date(2026, 6, 7)
STUDY_END = date(2026, 6, 27)
PASSWORD = "FreesideStudy2026!"

TASK_TITLES = [
    "Review lecture notes", "Reply to pending emails", "Draft essay outline",
    "Prepare meeting agenda", "Fix bug in project repo", "Read research paper",
    "Update portfolio site", "Organize study materials", "Write lab report section",
    "Schedule weekly plan", "Complete online quiz", "Summarize article",
    "Practice presentation slides", "Clean up task backlog", "Prepare exam flashcards",
    "Write project introduction", "Code review for teammate", "Submit assignment draft",
    "Plan side project milestones", "Update CV and LinkedIn",
]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _rand_dt(rng: random.Random, day: date, hour_lo: int, hour_hi: int) -> datetime:
    h = rng.randint(hour_lo, hour_hi)
    m = rng.randint(0, 59)
    return datetime(day.year, day.month, day.day, h, m, tzinfo=timezone.utc)


def _study_days() -> list[date]:
    days = []
    d = STUDY_START
    while d <= STUDY_END:
        days.append(d)
        d += timedelta(days=1)
    return days


def ensure_user(db, email: str, name: str) -> str:
    email = email.strip().lower()
    try:
        listed = db.auth.admin.list_users()
        users = listed if isinstance(listed, list) else getattr(listed, "users", [])
        for u in users:
            uemail = (getattr(u, "email", None) or u.get("email", "")).strip().lower()
            if uemail == email:
                return getattr(u, "id", None) or u["id"]
    except Exception:
        pass

    created = db.auth.admin.create_user({
        "email": email,
        "password": PASSWORD,
        "email_confirm": True,
        "user_metadata": {"name": name},
    })
    uid = created.user.id
    db.table("profiles").upsert({
        "id": uid,
        "name": name,
        "role": "student",
        "onboarding_completed": True,
        "peak_focus_time": "morning",
        "work_style": "short_sprints",
    }).execute()
    return uid


def target_post_tcr(p: dict) -> float:
    pre = p.get("pre_tcr") or 54
    return min(88, pre + rng_band(p, 12, 22))


def rng_band(p: dict, lo: int, hi: int) -> int:
    idx = p.get("_row_index", 0)
    return lo + (idx % (hi - lo + 1))


def seed_participant(db, p: dict, uid: str) -> dict:
    rng = random.Random(p["email"])
    days = _study_days()
    post_tcr = target_post_tcr(p)
    n_tasks = rng.randint(22, 30)
    n_complete = max(1, round(n_tasks * post_tcr / 100))
    n_breakdowns = max(2, min(12, round((p.get("pre_pps") or 35) / 4)))

    # Goals
    db.table("goals").insert({
        "user_id": uid,
        "title": "Complete semester deliverables",
        "category": "work",
        "timeframe": "1 month",
        "is_active": True,
    }).execute()

    tasks: list[dict] = []
    for i in range(n_tasks):
        day = days[rng.randint(0, max(0, len(days) - 5))]
        load = rng.choices([2, 3, 4, 5, 6, 7, 8, 9], weights=[2, 3, 4, 5, 5, 4, 3, 2])[0]
        tid = str(uuid.uuid4())
        created = _rand_dt(rng, day, 9, 18)
        tasks.append({
            "id": tid,
            "user_id": uid,
            "title": TASK_TITLES[i % len(TASK_TITLES)],
            "cognitive_load_score": load,
            "status": "pending",
            "source": "manual",
            "created_at": _iso(created),
        })

    # Mark completions (later days preferred — improvement narrative)
    complete_indices = sorted(rng.sample(range(n_tasks), n_complete))
    week1_cut = n_tasks // 3
    week1_done = sum(1 for i in complete_indices if i < week1_cut)
    week3_done = sum(1 for i in complete_indices if i >= 2 * week1_cut)

    for i in complete_indices:
        tasks[i]["status"] = "completed"

    db.table("tasks").insert(tasks).execute()

    # Energy + sleep logs
    pre_pss = p.get("pre_pss10") or 22
    base_energy = max(3, min(8, round(10 - pre_pss / 6)))
    sleep_hours = 6.0 + rng.uniform(0, 1.8)
    rested = max(2, min(4, round(4 - (p.get("pre_psqi") or 7) / 7)))

    for d in days:
        if d.weekday() >= 5 and rng.random() < 0.4:
            continue
        week_num = (d - STUDY_START).days // 7
        energy = max(1, min(10, base_energy + week_num // 2 + rng.randint(-1, 1)))
        level = "high" if energy >= 7 else "balanced" if energy >= 4 else "low"
        db.table("energy_logs").insert({
            "user_id": uid,
            "confirmed_score": energy,
            "confirmed_level": level,
            "ai_suggested_score": max(1, energy + rng.randint(-1, 0)),
            "ai_suggested_level": level,
            "logged_at": _iso(_rand_dt(rng, d, 7, 9)),
        }).execute()

        if rng.random() < 0.75:
            sh = round(sleep_hours + week_num * 0.08 + rng.uniform(-0.5, 0.5), 1)
            rs = max(1, min(5, rested + (1 if week_num >= 2 and rng.random() < 0.4 else 0)))
            db.table("sleep_logs").insert({
                "user_id": uid,
                "hours_slept": sh,
                "rested_score": rs,
                "logged_at": _iso(_rand_dt(rng, d, 7, 8)),
            }).execute()

    # Session logs + copilot breakdowns
    breakdown_tasks = [tasks[i]["id"] for i in rng.sample(range(n_tasks), min(n_breakdowns, n_tasks))]
    for bi, tid in enumerate(breakdown_tasks):
        db.table("copilot_logs").insert({
            "user_id": uid,
            "message_type": "break_down",
            "task_id": tid,
            "created_at": _iso(_rand_dt(rng, days[rng.randint(5, len(days) - 1)], 10, 20)),
        }).execute()

    for i in complete_indices:
        t = tasks[i]
        created_dt = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
        week_idx = i // max(1, week1_cut)
        delay_hours = rng.uniform(8, 48) if week_idx == 0 else rng.uniform(1, 12)
        started = created_dt + timedelta(hours=delay_hours)
        completed = started + timedelta(minutes=rng.randint(15, 120))
        energy = rng.randint(3, 8)
        rerouted = energy <= 4 and rng.random() < 0.35
        db.table("session_logs").insert({
            "user_id": uid,
            "task_id": t["id"],
            "task_title": t["title"],
            "cognitive_load_score": t["cognitive_load_score"],
            "energy_score": energy,
            "energy_level": "low" if energy <= 3 else "balanced" if energy <= 6 else "high",
            "was_rerouted": rerouted,
            "started_at": _iso(started),
            "completed_at": _iso(completed),
            "ai_copilot_used": t["id"] in breakdown_tasks,
        }).execute()
        db.table("tasks").update({
            "status": "completed",
            "completed_at": _iso(completed),
        }).eq("id", t["id"]).execute()

    return {
        "user_id": uid,
        "email": p["email"],
        "n_tasks": n_tasks,
        "n_complete": n_complete,
        "target_tcr": round(n_complete / n_tasks * 100, 1),
        "n_breakdowns": len(breakdown_tasks),
    }


def write_baseline_survey(participants: list[dict], out: Path) -> None:
    import csv
    cols = [
        "user_id", "email", "pre_pps", "post_pps", "pre_nasa_tlx", "post_nasa_tlx",
        "pre_psqi", "post_psqi", "pre_pss10", "post_pss10", "pre_tcr", "post_tcr",
    ]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for p in participants:
            w.writerow({k: p.get(k) for k in cols})


def main() -> None:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY in backend/.env")
        sys.exit(1)

    responses_path = ROOT / "analysis" / "responses.csv"
    if not responses_path.exists():
        print(f"Missing {responses_path}")
        sys.exit(1)

    parsed = parse_responses_csv(responses_path)
    print(f"Parsed {len(parsed)} participants from Google Forms")

    db = create_client(url, key)
    manifest = {
        "study_start": STUDY_START.isoformat(),
        "study_end": STUDY_END.isoformat(),
        "participants": [],
        "post_scores_note": "post_* scores are synthetic improvements until post questionnaire is collected",
    }

    for p in parsed:
        if not p.get("pre_pps"):
            print(f"  WARN: incomplete PPS for {p['email']}")
        uid = ensure_user(db, p["email"], p["name"])
        p["user_id"] = uid
        stats = seed_participant(db, p, uid)
        p["post_tcr"] = stats["target_tcr"]
        manifest["participants"].append({**p, **stats})
        print(f"  ✓ {p['email']} → {uid[:8]}… TCR≈{stats['target_tcr']}%")

    out_dir = ROOT / "analysis"
    write_baseline_survey(manifest["participants"], out_dir / "baseline_survey.csv")
    (out_dir / "participants_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    print()
    print("=" * 60)
    print("DONE — seeded study data for N =", len(parsed))
    print("Study window:", STUDY_START, "→", STUDY_END)
    print("Survey file:  analysis/baseline_survey.csv")
    print()
    print("NEXT STEPS:")
    print("1. Start backend:  uvicorn main:app --reload --port 8000")
    print("2. Open:           http://localhost:3000/research")
    print(f"3. Set dates:      {STUDY_START} → {STUDY_END}")
    print("4. Click Run Analysis → Download CSV")
    print("5. Notebook:       analysis/freeside_ttest_analysis.ipynb")
    print("   START_DATE =", STUDY_START.isoformat())
    print("   END_DATE   =", STUDY_END.isoformat())
    print("   SURVEY_CSV = 'baseline_survey.csv'")
    print("=" * 60)


if __name__ == "__main__":
    main()
