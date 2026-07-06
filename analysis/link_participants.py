#!/usr/bin/env python3
"""
Link real participant emails to Supabase user_ids for thesis analysis.

Usage:
  1. Fill analysis/participants_survey.csv with your 10 real rows (email + pre/post scores).
  2. Ensure each participant has a Freeside account with that email.
  3. Run from repo root:
       python analysis/link_participants.py analysis/participants_survey.csv

Outputs:
  analysis/baseline_survey.csv   — ready for freeside_ttest_analysis.ipynb
  analysis/participants_manifest.json — email → user_id map + warnings
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env", override=True)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
ADMIN_EMAIL = os.getenv("RESEARCH_ADMIN_EMAIL", "ninachkheidze19@gmail.com")

REQUIRED_SURVEY_COLS = [
    "email",
    "pre_pps",
    "post_pps",
    "pre_nasa_tlx",
    "post_nasa_tlx",
    "pre_psqi",
    "post_psqi",
    "pre_pss10",
    "post_pss10",
]

OUTPUT_COLS = ["user_id"] + [c for c in REQUIRED_SURVEY_COLS if c != "email"]


def fetch_auth_users() -> dict[str, dict]:
    resp = requests.get(
        f"{BACKEND_URL}/research/users",
        params={"admin_email": ADMIN_EMAIL},
        timeout=30,
    )
    resp.raise_for_status()
    users = resp.json().get("users", [])
    by_email: dict[str, dict] = {}
    for u in users:
        email = (u.get("email") or "").strip().lower()
        if email:
            by_email[email] = u
    return by_email


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python analysis/link_participants.py <participants_survey.csv>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    survey = pd.read_csv(input_path)
    missing = [c for c in REQUIRED_SURVEY_COLS if c not in survey.columns]
    if missing:
        print(f"Missing columns in {input_path}: {missing}")
        print(f"Required: {REQUIRED_SURVEY_COLS}")
        sys.exit(1)

    auth_by_email = fetch_auth_users()
    rows = []
    manifest = {"linked": [], "unmatched_emails": [], "admin_email": ADMIN_EMAIL}

    for _, row in survey.iterrows():
        email = str(row["email"]).strip().lower()
        auth = auth_by_email.get(email)
        if not auth:
            manifest["unmatched_emails"].append(email)
            continue
        rows.append({
            "user_id": auth["id"],
            "pre_pps": int(row["pre_pps"]),
            "post_pps": int(row["post_pps"]),
            "pre_nasa_tlx": int(row["pre_nasa_tlx"]),
            "post_nasa_tlx": int(row["post_nasa_tlx"]),
            "pre_psqi": int(row["pre_psqi"]),
            "post_psqi": int(row["post_psqi"]),
            "pre_pss10": int(row["pre_pss10"]),
            "post_pss10": int(row["post_pss10"]),
        })
        manifest["linked"].append({
            "user_id": auth["id"],
            "email": email,
            "name": row.get("name") or auth.get("display_name"),
            "pre_pps": int(row["pre_pps"]),
            "post_pps": int(row["post_pps"]),
        })

    out_dir = Path(__file__).resolve().parent
    baseline_path = out_dir / "baseline_survey.csv"
    manifest_path = out_dir / "participants_manifest.json"

    if not rows:
        print("No participants linked. Check emails and that backend is running.")
        sys.exit(1)

    pd.DataFrame(rows)[OUTPUT_COLS].to_csv(baseline_path, index=False)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Linked {len(rows)} / {len(survey)} participants")
    print(f"Wrote {baseline_path}")
    print(f"Wrote {manifest_path}")
    if manifest["unmatched_emails"]:
        print("UNMATCHED emails (no Freeside account):")
        for e in manifest["unmatched_emails"]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
