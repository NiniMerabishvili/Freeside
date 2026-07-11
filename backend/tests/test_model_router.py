from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import model_router


def _stub_usage(monkeypatch):
    monkeypatch.setattr(model_router, "_log_usage", lambda **_: None)


def test_generate_json_valid_response_passes(monkeypatch):
    _stub_usage(monkeypatch)

    def fake_dispatch(*args, **kwargs):
        return (
            '{"suggested_score": 7, "suggested_level": "high", "reasoning": "Open calendar."}',
            10,
            8,
        )

    monkeypatch.setattr(model_router, "_dispatch", fake_dispatch)

    result = model_router.generate_json("energy_inference", contents="prompt")

    assert result == {
        "suggested_score": 7,
        "suggested_level": "high",
        "reasoning": "Open calendar.",
    }


def test_generate_json_malformed_response_retries_then_succeeds(monkeypatch):
    _stub_usage(monkeypatch)
    calls: list[str] = []
    responses = [
        '{"suggested_score": 12, "suggested_level": "wired", "reasoning": ""}',
        '{"suggested_score": 5, "suggested_level": "balanced", "reasoning": "Moderate load."}',
    ]

    def fake_dispatch(*args, **kwargs):
        calls.append(str(kwargs["contents"]))
        return responses.pop(0), 10, 8

    monkeypatch.setattr(model_router, "_dispatch", fake_dispatch)

    result = model_router.generate_json("energy_inference", contents="prompt")

    assert result["suggested_score"] == 5
    assert len(calls) == 2
    assert "Return ONLY valid JSON matching this shape" in calls[1]


def test_generate_json_malformed_response_fails_twice(monkeypatch):
    _stub_usage(monkeypatch)

    def fake_dispatch(*args, **kwargs):
        return '{"suggested_score": 12, "suggested_level": "wired", "reasoning": ""}', 10, 8

    monkeypatch.setattr(model_router, "_dispatch", fake_dispatch)

    with pytest.raises(model_router.ModelResponseError) as exc:
        model_router.generate_json("energy_inference", contents="prompt")

    assert "failed validation after one retry" in str(exc.value)


def test_generate_text_wraps_unimplemented_anthropic(monkeypatch):
    _stub_usage(monkeypatch)
    monkeypatch.setitem(
        model_router.TASK_MODELS,
        "anthropic_test",
        model_router.ModelSpec(model_router.ANTHROPIC, "claude-sonnet-4.6"),
    )

    with pytest.raises(model_router.ModelResponseError) as exc:
        model_router.generate_text("anthropic_test", contents="prompt", retries=0)

    assert "Anthropic provider not configured yet" in str(exc.value)
