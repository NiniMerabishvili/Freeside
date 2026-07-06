"""Sleep pulse routes — daily sleep log for SQDS thesis metric."""
from datetime import date, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

router = APIRouter()

supabase = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)


class SleepLogRequest(BaseModel):
    user_id: str
    hours_slept: float = Field(ge=0, le=24)
    rested_score: int = Field(ge=1, le=5)


def _today_start_iso() -> str:
    return datetime.combine(date.today(), datetime.min.time()).isoformat()


@router.get("/today")
def get_today_sleep(user_id: str):
    """Return today's sleep pulse if the user already logged."""
    result = (
        supabase.table("sleep_logs")
        .select("hours_slept, rested_score, logged_at")
        .eq("user_id", user_id)
        .gte("logged_at", _today_start_iso())
        .order("logged_at", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        row = result.data[0]
        return {
            "logged_today": True,
            "hours_slept": float(row["hours_slept"]),
            "rested_score": row["rested_score"],
            "logged_at": row.get("logged_at"),
        }
    return {"logged_today": False}


@router.post("/log")
def log_sleep(request: SleepLogRequest):
    """Save or update today's sleep pulse (one entry per calendar day)."""
    payload = {
        "hours_slept": round(request.hours_slept, 1),
        "rested_score": request.rested_score,
        "logged_at": datetime.now().isoformat(),
    }

    existing = (
        supabase.table("sleep_logs")
        .select("id")
        .eq("user_id", request.user_id)
        .gte("logged_at", _today_start_iso())
        .order("logged_at", desc=True)
        .limit(1)
        .execute()
    )

    try:
        if existing.data:
            row_id = existing.data[0]["id"]
            result = (
                supabase.table("sleep_logs")
                .update(payload)
                .eq("id", row_id)
                .execute()
            )
        else:
            result = (
                supabase.table("sleep_logs")
                .insert({"user_id": request.user_id, **payload})
                .execute()
            )
    except Exception as exc:
        msg = str(exc).lower()
        if "sleep_logs" in msg and ("does not exist" in msg or "pgrst205" in msg):
            raise HTTPException(
                status_code=503,
                detail="Sleep logging is not set up yet. Run database/migrations/004_sleep_logs.sql in Supabase.",
            ) from exc
        raise HTTPException(status_code=500, detail="Could not save sleep log.") from exc

    if not result.data:
        raise HTTPException(status_code=500, detail="Could not save sleep log.")

    row = result.data[0]
    return {
        "status": "saved",
        "hours_slept": float(row["hours_slept"]),
        "rested_score": row["rested_score"],
        "logged_at": row.get("logged_at"),
    }
