"""Tests for AI model-output normalization and rejection rules."""

from app.ai.models import AITextAction
from app.ai.output_guard import normalize_model_output, validate_model_output


def test_extracts_supported_json_result_envelope():
    assert normalize_model_output('{"translation": "你好"}') == "你好"


def test_rejects_request_payload_echo():
    raw = '{"task":"translate","source_language":"auto","target_language":"zh-CN","source_text":"Hello"}'
    result = validate_model_output(raw, source_text="Hello", action=AITextAction.TRANSLATE)
    assert result.valid is False
    assert result.reason == "request_payload_echo"


def test_removes_markdown_fence_and_label():
    result = validate_model_output(
        "```text\nTranslation: 你好\n```",
        source_text="Hello",
        action=AITextAction.TRANSLATE,
    )
    assert result.valid is True
    assert result.text == "你好"


def test_rejects_unchanged_translation_source():
    result = validate_model_output(
        "Hello world",
        source_text="Hello world",
        action=AITextAction.TRANSLATE,
    )
    assert result.valid is False
    assert result.reason == "unchanged_source"


def test_rejects_empty_output():
    result = validate_model_output("   ", source_text="Hello", action=AITextAction.TRANSLATE)
    assert result.valid is False
    assert result.reason == "empty_output"
