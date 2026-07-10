"""
Manual test harness for the Freeside Copilot pipeline (Phase 6).

Run from the backend/ directory:

    # Offline checks only (no API keys needed) — parsers + task-card extraction
    python scripts/test_freeside_copilot.py

    # Full live run against a real user (needs GEMINI_API_KEY + connected integrations)
    python scripts/test_freeside_copilot.py --user-id <supabase-user-uuid>
    python scripts/test_freeside_copilot.py --user-id <uuid> --message "I need to write a report on user research findings"
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure the backend root is importable when run as scripts/…
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The Copilot replies with emoji (📋 ⏱ 🧠); force UTF-8 so Windows consoles
# (cp1252) don't crash when printing them.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

from services.copilot_actions import (  # noqa: E402
    extract_energy_profile,
    extract_task_cards,
    parse_copilot_actions,
    strip_structured_blocks,
    task_cards_to_suggestions,
)

_SAMPLE_REPLY = """<energy_profile>
  score: 48
  level: LOW
  key_factors: ["4 meetings today", "high fragmentation"]
  recommended_work_style: Keep it light and short today.
</energy_profile>

Sounds like a solid focus block. Here's how I'd slot it in:

<task_card>
title: Write user research findings report
estimated_minutes: 90
cognitive_weight: 4
proposed_date: 2026-07-11
proposed_time_slot: 09:00–10:30
source: copilot_chat
deadline: 2026-07-15
notes: Deep-work morning slot while your calendar is open
conflict_warning: null
</task_card>

I also Moved 'Reply to vendor emails' to Monday to keep this morning clear, and
Split 'Quarterly review prep' into a research pass and a drafting pass.
"""


def _hr(label: str) -> None:
    print("\n" + "=" * 70)
    print(label)
    print("=" * 70)


def test_offline() -> None:
    _hr("3. Task card extraction (offline)")
    cards = extract_task_cards(_SAMPLE_REPLY)
    print(f"Extracted {len(cards)} card(s):")
    for c in cards:
        print("  -", c)
    assert cards and cards[0].get("title"), "Expected at least one task card with a title"

    _hr("5. Action parser (offline)")
    actions = parse_copilot_actions(_SAMPLE_REPLY)
    print(f"Detected {len(actions)} action(s):")
    for a in actions:
        print("  -", a)
    assert any(a["type"] == "reschedule" for a in actions), "Expected a reschedule action"
    assert any(a["type"] == "split" for a in actions), "Expected a split action"

    _hr("6. Energy profile + tag stripping (offline)")
    profile = extract_energy_profile(_SAMPLE_REPLY)
    print("energy_profile:", profile)
    assert profile and profile.get("level") == "LOW", "Expected a LOW energy profile"

    suggestions = task_cards_to_suggestions(cards)
    print("suggestions:", suggestions)
    assert suggestions and suggestions[0]["cognitive_load_score"] == 8, "Expected weight 4 -> load 8"

    clean = strip_structured_blocks(_SAMPLE_REPLY)
    print("\nclean reply (what the user sees):\n" + clean)
    assert "<task_card>" not in clean and "<energy_profile>" not in clean, "Tags must be stripped"
    assert "Moved 'Reply to vendor emails'" in clean, "Human-facing lines must remain"
    print("\nOffline checks passed.")


def test_live(user_id: str, message: str) -> None:
    from supabase import create_client
    from services.context_builder import build_context_for_user
    from services.copilot import chat_with_copilot_for_user

    db = create_client(
        os.getenv("SUPABASE_URL", ""),
        os.getenv("SUPABASE_SERVICE_KEY", ""),
    )

    _hr("1. Context builder")
    context = build_context_for_user(db, user_id)
    print(context)

    _hr("2. Chat turn")
    reply, history = chat_with_copilot_for_user(db, user_id, message, [])
    print(reply)

    _hr("3. Task card extraction (live reply)")
    for c in extract_task_cards(reply):
        print("  -", c)

    _hr("4. Low-energy scenario")
    reply2, _ = chat_with_copilot_for_user(
        db, user_id, "I'm running on empty today — what should I work on?", history
    )
    print(reply2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeside Copilot manual test harness")
    parser.add_argument("--user-id", dest="user_id", help="Supabase user UUID for a live run")
    parser.add_argument(
        "--message",
        default="I need to write a report on user research findings",
        help="First user message for the live chat turn",
    )
    args = parser.parse_args()

    test_offline()
    if args.user_id:
        test_live(args.user_id, args.message)
    else:
        print("\n(Skipping live run — pass --user-id <uuid> to exercise the Gemini path.)")


if __name__ == "__main__":
    main()
