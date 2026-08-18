import json

import pytest

from app.ai.errors import AIConfigurationError, AIResponseError
from app.ai.models import AITextAction, AITextRequest
from app.ai.provider import (
    POLISH_TEMPERATURE,
    TRANSLATE_TEMPERATURE,
    DeepSeekTextProvider,
)


class FakeDeepSeekClient:
    model = "deepseek-v4-flash"

    def __init__(self, output="generated text"):
        self.output = output
        self.calls = []
        self.closed = False

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        return self.output

    def close(self):
        self.closed = True


def test_translate_dispatches_to_client_with_translation_prompt():
    client = FakeDeepSeekClient("你好")
    provider = DeepSeekTextProvider(client)

    result = provider.execute(
        AITextRequest(
            "Hello",
            AITextAction.TRANSLATE,
            source_language="en",
            target_language="zh-CN",
            request_id=8,
        )
    )

    call = client.calls[0]
    payload = json.loads(call["user_prompt"])
    assert call["temperature"] == TRANSLATE_TEMPERATURE
    assert payload["task"] == "translate"
    assert result.output_text == "你好"
    assert result.provider == "deepseek"
    assert result.model == "deepseek-v4-flash"
    assert result.request_id == 8


def test_polish_dispatches_with_style_and_same_language_intent():
    client = FakeDeepSeekClient("This is a test.")
    provider = DeepSeekTextProvider(client)

    result = provider.execute(
        AITextRequest(
            "This are a test.",
            AITextAction.POLISH,
            source_language="en",
            style="academic",
        )
    )

    call = client.calls[0]
    payload = json.loads(call["user_prompt"])
    assert call["temperature"] == POLISH_TEMPERATURE
    assert payload["task"] == "polish"
    assert payload["style"] == "academic"
    assert result.style == "academic"


def test_provider_rejects_empty_source_text():
    provider = DeepSeekTextProvider(FakeDeepSeekClient())

    with pytest.raises(AIConfigurationError):
        provider.execute(AITextRequest("   ", AITextAction.TRANSLATE))


def test_provider_rejects_empty_client_output():
    provider = DeepSeekTextProvider(FakeDeepSeekClient("   "))

    with pytest.raises(AIResponseError):
        provider.execute(AITextRequest("Hello", AITextAction.TRANSLATE))


def test_provider_close_delegates_to_client():
    client = FakeDeepSeekClient()
    provider = DeepSeekTextProvider(client)

    provider.close()

    assert client.closed is True
