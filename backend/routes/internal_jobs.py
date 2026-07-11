"""Internal job endpoints triggered by schedulers."""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException
from supabase import create_client

from services.burnout_model import score_all_active_users

router = APIRouter()

supabase = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)


def _require_job_secret(authorization: str | None) -> None:
    expected = os.getenv("INTERNAL_JOB_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="INTERNAL_JOB_SECRET is not configured")
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/burnout-nightly")
def burnout_nightly(authorization: str | None = Header(default=None)):
    _require_job_secret(authorization)
    return score_all_active_users(supabase)
