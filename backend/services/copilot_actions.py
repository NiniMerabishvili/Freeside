"""
Freeside Copilot output parsing + write-back (Phases 4 & 5).

- Phase 4: parse <task_card> blocks the model emits, and write confirmed tasks
  back to ClickUp and/or Google Calendar.
- Phase 5: parse natural-language reschedule / split intents from the reply.

Repo-native adaptations: ClickUp writes go through httpx + the shared auth
header helper; Calendar writes build credentials from a stored refresh token.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from services.clickup import CLICKUP_API, _headers
from services.context_builder import _credentials_from_refresh_token

logger = logging.getLogger(__name__)

# The prompt emits task_card.cognitive_weight as an integer 1–5 (5 = heaviest).
# ClickUp priority ids are inverted: 1=urgent, 2=high, 3=normal, 4=low.
_WEIGHT_TO_PRIORITY = {5: 1, 4: 2, 3: 3, 2: 4, 1: 4}
# Also accept the light/moderate/deep vocabulary as a fallback.
_LABEL_TO_PRIORITY = {"deep": 2, "moderate": 3, "light": 4}

# Values the prompt may emit that mean "no concrete value".
_EMPTY_VALUES = {"", "null", "none", "open", "n/a"}

_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


def _priority_from_weight(task_card: dict) -> int:
    """Map a task card's cognitive_weight (int 1–5 or label) to a ClickUp priority."""
    raw = str(task_card.get("cognitive_weight", "")).strip().lower()
    if raw in _LABEL_TO_PRIORITY:
        return _LABEL_TO_PRIORITY[raw]
    try:
        return _WEIGHT_TO_PRIORITY.get(int(float(raw)), 3)
    except (TypeError, ValueError):
        return 3


# ---------------------------------------------------------------------------
# Phase 4 · Step 1 — Task card parser
# ---------------------------------------------------------------------------

def extract_task_cards(copilot_response: str) -> list[dict]:
    """Parse every <task_card>…</task_card> block into a flat key/value dict."""
    cards: list[dict] = []
    for block in re.findall(r"<task_card>(.*?)</task_card>", copilot_response or "", re.DOTALL):
        card: dict[str, str] = {}
        for line in block.strip().split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                value = value.strip()
                # Strip a single pair of surrounding quotes the model may add.
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1].strip()
                card[key.strip()] = value
        if card:
            cards.append(card)
    return cards


# ---------------------------------------------------------------------------
# Phase 4 · Step 2 — Write confirmed task to ClickUp
# ---------------------------------------------------------------------------

def _date_to_ms(value: str | None) -> int | None:
    """Convert a 'YYYY-MM-DD' (or ISO) string into epoch milliseconds (UTC)."""
    if not value:
        return None
    raw = value.strip()
    if raw.lower() in _EMPTY_VALUES:
        return None
    try:
        if "T" in raw:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
        else:
            dt = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def create_clickup_task(api_token: str, list_id: str, task_card: dict) -> dict:
    """Create a ClickUp task from a parsed task card."""
    try:
        estimated_minutes = int(task_card.get("estimated_minutes", 60))
    except (TypeError, ValueError):
        estimated_minutes = 60

    priority = _priority_from_weight(task_card)

    payload: dict = {
        "name": task_card.get("title", "Untitled task"),
        "description": task_card.get("notes", ""),
        "priority": priority,
        "time_estimate": estimated_minutes * 60_000,
        "tags": ["copilot-created"],
    }
    due_ms = _date_to_ms(task_card.get("deadline")) or _date_to_ms(task_card.get("proposed_date"))
    if due_ms is not None:
        payload["due_date"] = due_ms

    with httpx.Client(timeout=25) as client:
        response = client.post(
            f"{CLICKUP_API}/list/{list_id}/task",
            headers=_headers(api_token),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def resolve_default_list_id(api_token: str, team_id: str) -> str | None:
    """
    Find a usable ClickUp list id for the team (needed because the repo stores a
    team id, not a list id). Walks spaces → folderless lists, then
    folders → lists, and returns the first list found.
    """
    with httpx.Client(timeout=25) as client:
        spaces = (
            client.get(f"{CLICKUP_API}/team/{team_id}/space", headers=_headers(api_token))
            .json()
            .get("spaces", [])
        )
        for space in spaces:
            space_id = space.get("id")
            if not space_id:
                continue
            folderless = (
                client.get(f"{CLICKUP_API}/space/{space_id}/list", headers=_headers(api_token))
                .json()
                .get("lists", [])
            )
            if folderless:
                return folderless[0]["id"]
            folders = (
                client.get(f"{CLICKUP_API}/space/{space_id}/folder", headers=_headers(api_token))
                .json()
                .get("folders", [])
            )
            for folder in folders:
                lists = folder.get("lists", [])
                if lists:
                    return lists[0]["id"]
    return None


# ---------------------------------------------------------------------------
# Phase 4 · Step 3 — Write confirmed task to Google Calendar
# ---------------------------------------------------------------------------

def _split_time_slot(slot: str) -> tuple[str | None, str | None]:
    """
    Split 'HH:MM–HH:MM' (en dash or hyphen) into (start, end).

    Returns (None, None) for non-time slots like 'open' so the caller can fall
    back to a default start time.
    """
    if not slot or slot.strip().lower() in _EMPTY_VALUES:
        return None, None
    parts = re.split(r"\s*[–-]\s*", slot.strip(), maxsplit=1)
    start = parts[0].strip() if parts and _TIME_RE.match(parts[0].strip()) else None
    end = parts[1].strip() if len(parts) > 1 and _TIME_RE.match(parts[1].strip()) else None
    return start, end


def create_calendar_event(
    credentials: str | Credentials,
    task_card: dict,
    *,
    timezone_name: str = "UTC",
) -> dict:
    """Create a Google Calendar event from a parsed task card."""
    creds = (
        _credentials_from_refresh_token(credentials)
        if isinstance(credentials, str)
        else credentials
    )
    service = build("calendar", "v3", credentials=creds)

    proposed_date = task_card.get("proposed_date") or date.today().isoformat()
    start_str, end_str = _split_time_slot(task_card.get("proposed_time_slot", ""))
    start_str = start_str or "09:00"

    try:
        estimated_minutes = int(task_card.get("estimated_minutes", 60))
    except (TypeError, ValueError):
        estimated_minutes = 60

    start_dt = datetime.fromisoformat(f"{proposed_date}T{start_str}:00")
    if end_str:
        try:
            end_dt = datetime.fromisoformat(f"{proposed_date}T{end_str}:00")
        except ValueError:
            end_dt = start_dt + timedelta(minutes=estimated_minutes)
    else:
        end_dt = start_dt + timedelta(minutes=estimated_minutes)

    event = {
        "summary": task_card.get("title", "Freeside task"),
        "description": task_card.get("notes", "Added by Freeside Copilot"),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone_name},
    }
    return service.events().insert(calendarId="primary", body=event).execute()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Phase 5 — Natural-language action parser (reschedule / split)
# ---------------------------------------------------------------------------

def parse_copilot_actions(copilot_response: str) -> list[dict]:
    """Detect reschedule/split intents the model states in plain language."""
    actions: list[dict] = []
    text = copilot_response or ""

    for task_title, target_day in re.findall(r"Moved '(.+?)' to (\w+)", text):
        actions.append({
            "type": "reschedule",
            "task_title": task_title,
            "target_day": target_day,
        })

    for task_title in re.findall(r"Split '(.+?)' into", text):
        actions.append({"type": "split", "task_title": task_title})

    return actions


# ---------------------------------------------------------------------------
# Energy profile parsing + tag stripping (for clean, user-language display)
# ---------------------------------------------------------------------------

def extract_energy_profile(copilot_response: str) -> dict | None:
    """Parse the <energy_profile>…</energy_profile> block into a dict, if present."""
    match = re.search(
        r"<energy_profile>(.*?)</energy_profile>", copilot_response or "", re.DOTALL
    )
    if not match:
        return None
    profile: dict[str, str] = {}
    for line in match.group(1).strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            profile[key.strip()] = value.strip()
    return profile or None


def strip_structured_blocks(copilot_response: str) -> str:
    """
    Remove machine-readable blocks so only natural-language prose remains for
    display. Keeps the model's friendly summaries (e.g. the 📋 task display and
    "Moved '…' to …" lines) intact — those are already human-facing.
    """
    if not copilot_response:
        return ""
    out = re.sub(r"<energy_profile>.*?</energy_profile>", "", copilot_response, flags=re.DOTALL)
    out = re.sub(r"<task_card>.*?</task_card>", "", out, flags=re.DOTALL)
    out = re.sub(r"</?freeside_context>", "", out)
    # Drop any orphaned closing/opening structured tags left on their own line.
    out = re.sub(r"^\s*</?(energy_profile|task_card)>\s*$", "", out, flags=re.MULTILINE)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _card_load(card: dict) -> int:
    """Map a task card's cognitive_weight (1–5 or label) onto a 1–10 load score."""
    raw = str(card.get("cognitive_weight", "")).strip().lower()
    labels = {"light": 3, "moderate": 6, "deep": 9}
    if raw in labels:
        return labels[raw]
    try:
        return max(1, min(10, int(float(raw)) * 2))
    except (TypeError, ValueError):
        return 5


def task_cards_to_suggestions(cards: list[dict]) -> list[dict]:
    """
    Convert parsed <task_card> blocks into the {title, cognitive_load_score,
    estimated_minutes} shape the dashboard's suggestion panel already consumes.
    """
    suggestions: list[dict] = []
    for card in cards:
        title = (card.get("title") or "").strip()
        if not title:
            continue
        try:
            minutes = int(card.get("estimated_minutes", 60))
        except (TypeError, ValueError):
            minutes = 60
        suggestions.append({
            "title": title[:200],
            "cognitive_load_score": _card_load(card),
            "estimated_minutes": max(5, min(240, minutes)),
        })
    return suggestions
