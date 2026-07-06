"""
Research export routes — thesis data aggregation endpoints.
Restricted to service-role callers; not exposed to the frontend.
"""
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client
import io

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from services.metrics import export_thesis_data

router = APIRouter()

supabase = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)


ADMIN_EMAIL = "ninachkheidze19@gmail.com"


class ExportRequest(BaseModel):
    admin_email: str
    user_ids: list[str]
    start_date: date
    end_date: date


# ---------------------------------------------------------------------------
# GET /research/users
# Returns all user_ids that have any activity in the system.
# Used by the admin research dashboard to auto-populate the cohort.
# ---------------------------------------------------------------------------
@router.get("/users")
def list_research_users(admin_email: str = Query(...)):
    """
    Returns all registered users.
    Uses the Supabase auth admin API so every account appears — even those
    whose profile row was not created by the trigger (e.g. early accounts).
    Enriches with display_name from the profiles table where available.
    """
    if admin_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin access required.")

    # --- Pull all auth accounts via the admin API (service key required) ---
    try:
        auth_resp = supabase.auth.admin.list_users()
        auth_users = auth_resp if isinstance(auth_resp, list) else getattr(auth_resp, "users", [])
    except Exception:
        auth_users = []

    # --- Pull profile rows for display names --------------------------------
    profile_resp = (
        supabase.table("profiles")
        .select("id, name, created_at")
        .execute()
    )
    profile_map: dict = {
        p["id"]: p for p in (profile_resp.data or [])
    }

    # --- Merge: prefer profile name → auth email local part → UUID prefix ---
    users = []
    for au in auth_users:
        uid = getattr(au, "id", None) or au.get("id")
        email = getattr(au, "email", None) or au.get("email", "")
        created = (
            getattr(au, "created_at", None)
            or au.get("created_at", "")
        )
        # created_at may be a datetime object
        if hasattr(created, "isoformat"):
            created = created.isoformat()

        profile = profile_map.get(uid, {})
        name = profile.get("name") or (email.split("@")[0] if email else None) or uid[:8]

        users.append({
            "id":           uid,
            "display_name": name,
            "email":        email,
            "created_at":   created,
        })

    # Sort by created_at ascending
    users.sort(key=lambda u: u.get("created_at") or "")
    return {"users": users, "count": len(users)}


# ---------------------------------------------------------------------------
# POST /research/export/json
# Returns wide-format JSON — load directly into pandas with pd.DataFrame(rows)
# ---------------------------------------------------------------------------
@router.post("/export/json")
def export_json(req: ExportRequest):
    """
    Aggregate all 5 behavioral metrics for the provided cohort and return
    wide-format JSON.

    Example pandas usage:
        import pandas as pd, requests
        resp = requests.post("http://localhost:8000/research/export/json", json={...})
        df   = pd.DataFrame(resp.json()["rows"])
        survey = pd.read_csv("baseline_survey.csv")
        merged = survey.merge(df, on="user_id", how="inner")
    """
    if req.admin_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin access required.")
    if not req.user_ids:
        raise HTTPException(status_code=400, detail="user_ids must not be empty.")
    if req.start_date > req.end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date.")

    result = export_thesis_data(supabase, req.user_ids, req.start_date, req.end_date)
    return result


# ---------------------------------------------------------------------------
# POST /research/export/csv
# Streams a .csv file — download directly and open in Excel / pandas
# ---------------------------------------------------------------------------
@router.post("/export/csv")
def export_csv(req: ExportRequest):
    """
    Same aggregation as /export/json but returns a downloadable CSV file.

    Example pandas usage:
        import pandas as pd
        df = pd.read_csv("freeside_behavioral_data.csv")
    """
    if req.admin_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin access required.")
    if not req.user_ids:
        raise HTTPException(status_code=400, detail="user_ids must not be empty.")
    if req.start_date > req.end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date.")

    result = export_thesis_data(supabase, req.user_ids, req.start_date, req.end_date)

    filename = (
        f"freeside_behavioral_{req.start_date}_{req.end_date}"
        f"_n{result['cohort_size']}.csv"
    )

    return StreamingResponse(
        io.StringIO(result["csv_string"]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
