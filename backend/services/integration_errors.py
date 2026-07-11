"""
Typed integration sync errors (Phase 0 - Trust & Reliability).

Taxonomy:
- Service code raises SyncIntegrationError subclasses when an external
  integration fails in an expected way.
- Route handlers translate those typed errors into HTTP status codes.
- Context builders may catch typed errors at the user-facing boundary and
  convert them into SyncWarning objects so Co-Pilot can continue with a visible
  "using last known state" warning instead of silently hiding the failure.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class SyncErrorCode(str, Enum):
    CALENDAR_AUTH_REVOKED = "calendar_auth_revoked"
    CALENDAR_FETCH_FAILED = "calendar_fetch_failed"
    CALENDAR_NOT_CONNECTED = "calendar_not_connected"
    CLICKUP_AUTH_FAILED = "clickup_auth_failed"
    CLICKUP_FETCH_FAILED = "clickup_fetch_failed"
    CLICKUP_NOT_CONNECTED = "clickup_not_connected"
    CLICKUP_NO_WORKSPACE = "clickup_no_workspace"


SYNC_ERROR_MESSAGES: dict[SyncErrorCode, str] = {
    SyncErrorCode.CALENDAR_AUTH_REVOKED: (
        "Google Calendar access expired - reconnect in Settings to restore AI energy inference."
    ),
    SyncErrorCode.CALENDAR_FETCH_FAILED: (
        "Calendar sync failed, using last known state."
    ),
    SyncErrorCode.CALENDAR_NOT_CONNECTED: (
        "Google Calendar is not connected - connect it in Settings for smarter energy suggestions."
    ),
    SyncErrorCode.CLICKUP_AUTH_FAILED: (
        "ClickUp access expired - reconnect in Settings to sync your tasks."
    ),
    SyncErrorCode.CLICKUP_FETCH_FAILED: (
        "ClickUp sync failed, using tasks already in Freeside."
    ),
    SyncErrorCode.CLICKUP_NOT_CONNECTED: (
        "ClickUp is not connected - connect it in Settings to import assigned tasks."
    ),
    SyncErrorCode.CLICKUP_NO_WORKSPACE: (
        "ClickUp is connected but no workspace is selected - pick one in Settings."
    ),
}


@dataclass
class SyncWarning:
    code: SyncErrorCode
    message: str
    integration: str

    def to_dict(self) -> dict:
        return {
            "code": self.code.value,
            "message": self.message,
            "integration": self.integration,
        }


class SyncIntegrationError(Exception):
    """Base class for typed integration failures."""

    integration: Literal["calendar", "clickup"]

    def __init__(
        self,
        code: SyncErrorCode,
        message: str,
        integration: Literal["calendar", "clickup"],
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.integration = integration
        self.cause = cause

    def to_warning(self) -> SyncWarning:
        return SyncWarning(self.code, self.message, self.integration)


class CalendarSyncError(SyncIntegrationError):
    """Google Calendar auth or fetch failure."""

    def __init__(
        self,
        code: SyncErrorCode = SyncErrorCode.CALENDAR_FETCH_FAILED,
        message: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            code,
            message or SYNC_ERROR_MESSAGES[code],
            "calendar",
            cause=cause,
        )


class ClickUpAuthError(SyncIntegrationError):
    """ClickUp token is expired, revoked, or unauthorized."""

    def __init__(
        self,
        code: SyncErrorCode = SyncErrorCode.CLICKUP_AUTH_FAILED,
        message: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            code,
            message or SYNC_ERROR_MESSAGES[code],
            "clickup",
            cause=cause,
        )


class ClickUpSyncError(SyncIntegrationError):
    """ClickUp fetch/sync failed for a non-auth reason."""

    def __init__(
        self,
        code: SyncErrorCode = SyncErrorCode.CLICKUP_FETCH_FAILED,
        message: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            code,
            message or SYNC_ERROR_MESSAGES[code],
            "clickup",
            cause=cause,
        )


def calendar_warning_from_exception(exc: Exception) -> SyncWarning:
    if isinstance(exc, SyncIntegrationError):
        return exc.to_warning()
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
    if isinstance(exc, SyncIntegrationError):
        return exc.to_warning()
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
