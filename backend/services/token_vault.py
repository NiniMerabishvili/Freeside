"""Service-role token vault for encrypted OAuth/API secrets.

The SQL migration stores encrypted bytes in Postgres via pgcrypto and exposes
service-role-only RPCs. Backend code should use this module instead of reading
or writing plaintext token columns directly.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

_DEFAULT_DB = None


def _db():
    global _DEFAULT_DB
    if _DEFAULT_DB is None:
        _DEFAULT_DB = create_client(
            os.getenv("SUPABASE_URL", ""),
            os.getenv("SUPABASE_SERVICE_KEY", ""),
        )
    return _DEFAULT_DB


def _client(db: Any | None = None):
    return db if db is not None else _db()


def _encryption_key() -> str:
    key = os.getenv("ENCRYPTION_KEY", "")
    if len(key) < 16:
        raise RuntimeError("ENCRYPTION_KEY must be set to at least 16 characters.")
    return key


def _rpc_scalar(response: Any) -> str | None:
    data = getattr(response, "data", None)
    if data is None or data == "":
        return None
    return str(data)


def get_google_refresh_token(user_id: str, db: Any | None = None) -> str | None:
    """Return a decrypted Google refresh token for a user, if one exists."""
    resp = _client(db).rpc(
        "get_google_refresh_token",
        {"p_user_id": user_id, "p_key": _encryption_key()},
    ).execute()
    return _rpc_scalar(resp)


def set_google_refresh_token(
    user_id: str,
    refresh_token: str | None,
    db: Any | None = None,
) -> None:
    """Encrypt and store a Google refresh token, or clear it when None."""
    _client(db).rpc(
        "set_google_refresh_token",
        {
            "p_user_id": user_id,
            "p_token": refresh_token,
            "p_key": _encryption_key(),
        },
    ).execute()


def get_api_token(
    user_id: str,
    db: Any | None = None,
    *,
    integration_type: str = "clickup",
) -> str | None:
    """Return a decrypted integration API/OAuth token for a user."""
    resp = _client(db).rpc(
        "get_api_token",
        {
            "p_user_id": user_id,
            "p_key": _encryption_key(),
            "p_integration_type": integration_type,
        },
    ).execute()
    return _rpc_scalar(resp)


def set_api_token(
    user_id: str,
    api_token: str | None,
    db: Any | None = None,
    *,
    integration_type: str = "clickup",
) -> None:
    """Encrypt and store an integration token, or clear it when None."""
    _client(db).rpc(
        "set_api_token",
        {
            "p_user_id": user_id,
            "p_token": api_token,
            "p_key": _encryption_key(),
            "p_integration_type": integration_type,
        },
    ).execute()
