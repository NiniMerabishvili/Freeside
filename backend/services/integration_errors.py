"""
Typed integration sync errors (Phase 0 — Trust & Reliability).

Replaces silent `except: return []` degradation with explicit, user-facing error
codes the frontend can render as dismissible banners.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SyncErrorCode(str, Enum):
    CALENDAR_AUTH_REVOKED = "calendar_auth_revoked"
    CALENDAR_FETCH_FAILED = "calendar_fetch_failed"
    CALENDAR_NOT_CONNECTED = "calendar_not_connected"
    CLICKUP_AUTH_FAILED = "clickup_auth_failed"
    CLICKUP_FETCH_FAILED = "clickup_fetch_failed"
    CLICKUP_NOT_CONNECTED = "clickup_not_connected"
    CLICKUP_NO_WORKSPACE = "clickup_no_workspace"


# Default user-facing copy (English). Frontend may localize via code lookup.
SYNC_ERROR_MESSAGES: dict[SyncErrorCode, str] = {
    SyncErrorCode.CALENDAR_AUTH_REVOKED: (
        "Google Calendar access expired — reconnect in Settings to restore AI energy inference."
    ),
    SyncErrorCode.CALENDAR_FETCH_FAILED: (
        "Could not load your calendar today — using manual energy for now."
    ),
    SyncErrorCode.CALENDAR_NOT_CONNECTED: (
        "Google Calendar is not connected — connect it in Settings for smarter energy suggestions."
    ),
    SyncErrorCode.CLICKUP_AUTH_FAILED: (
        "ClickUp access expired — reconnect in Settings to sync your tasks."
    ),
    SyncErrorCode.CLICKUP_FETCH_FAILED: (
        "Could not sync ClickUp tasks right now — showing tasks already in Freeside."
    ),
    SyncErrorCode.CLICKUP_NOT_CONNECTED: (
        "ClickUp is not connected — connect it in Settings to import assigned tasks."
    ),
    SyncErrorCode.CLICKUP_NO_WORKSPACE: (
        "ClickUp is connected but no workspace is selected — pick one in Settings."
    ),
}


@dataclass
class SyncWarning:
    code: SyncErrorCode
    message: str
    integration: str  # "calendar" | "clickup"

    def to_dict(self) -> dict:
        return {
            "code": self.code.value,
            "message": self.message,
            "integration": self.integration,
        }


def calendar_warning_from_exception(exc: Exception) -> SyncWarning:
    text = str(exc).lower()
    if "invalid_grant" in text or "revoked" in text or "token" in text:
        return SyncWarning(
            SyncErrorCode.CALENDAR_AUTH_REVOKED,
            SYNC_ERROR_MESSAGES[SyncErrorCode.CALENDAR_AUTH_REVOKED],
            "calendar",
        )
    return SyncWarning(
        SyncErrorCode.CALENDAR_FETCH_FAILED,
        SYNC_ERROR_MESSAGES[SyncErrorCode.CALENDAR_FETCH_FAILED],
        "calendar",
    )


def clickup_warning_from_exception(exc: Exception) -> SyncWarning:
    text = str(exc).lower()
    if "401" in text or "403" in text or "unauthorized" in text or "invalid" in text:
        return SyncWarning(
            SyncErrorCode.CLICKUP_AUTH_FAILED,
            SYNC_ERROR_MESSAGES[SyncErrorCode.CLICKUP_AUTH_FAILED],
            "clickup",
        )
    return SyncWarning(
        SyncErrorCode.CLICKUP_FETCH_FAILED,
        SYNC_ERROR_MESSAGES[SyncErrorCode.CLICKUP_FETCH_FAILED],
        "clickup",
    )
