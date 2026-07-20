from __future__ import annotations

from services.copilot import _current_message_language_directive, _detect_response_language


def test_current_message_language_overrides_browser_hint():
    assert _detect_response_language("Plan my day", "ka-GE") == "English"
    assert _detect_response_language("Plan my day", "en") == "English"
    assert _detect_response_language("დამიგეგმე დღე", "en-US") == "Georgian"
    assert _detect_response_language("დამიგეგმე დღე", "ka") == "Georgian"


def test_language_directive_names_current_message_language():
    english = _current_message_language_directive("ka-GE", "What should I do first?")
    georgian = _current_message_language_directive("en-US", "რა გავაკეთო პირველად?")

    assert "current user message language is English" in english
    assert "reply in English" in english
    assert "current user message language is Georgian" in georgian
    assert "reply in Georgian" in georgian
