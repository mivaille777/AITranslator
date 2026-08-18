from dataclasses import FrozenInstanceError

import pytest

from app.ai.models import AITextAction, AITextRequest, AITextResult


def test_request_defaults_are_provider_independent():
    request = AITextRequest("hello", AITextAction.TRANSLATE)

    assert request.source_language == "auto"
    assert request.target_language == "zh-CN"
    assert request.style == "general"
    assert request.request_id == 0


def test_result_text_alias_returns_output():
    result = AITextResult(
        source_text="hello",
        output_text="你好",
        action=AITextAction.TRANSLATE,
        provider="deepseek",
        model="deepseek-v4-flash",
    )

    assert result.text == "你好"


def test_models_are_frozen():
    request = AITextRequest("hello", AITextAction.POLISH)

    with pytest.raises(FrozenInstanceError):
        request.source_text = "changed"
