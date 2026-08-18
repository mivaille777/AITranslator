import json

import pytest

from app.ai.errors import AIConfigurationError, AIResponseError
from app.ai.models import AITextAction, AITextRequest
from app.ai.provider import (
    POLISH_TEMPERATURE,
    STRICT_RETRY_TEMPERATURE,
    TRANSLATE_TEMPERATURE,
    DeepSeekTextProvider,
)


class FakeDeepSeekClient:
    model = "deepseek-v4-flash"

    def __init__(self, output="generated text"):
        self.outputs = list(output) if isinstance(output, (list, tuple)) else None
        self.output = output if self.outputs is None else None
        self.calls = []
        self.closed = False

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        if self.outputs is not None:
            return self.outputs.pop(0)
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


def test_invalid_first_output_triggers_strict_retry():
    payload_echo = '{"task":"translate","source_language":"en","target_language":"zh-CN","source_text":"Hello"}'
    client = FakeDeepSeekClient([payload_echo, "你好"])
    provider = DeepSeekTextProvider(client)

    result = provider.execute(
        AITextRequest("Hello", AITextAction.TRANSLATE, source_language="en")
    )

    assert result.output_text == "你好"
    assert len(client.calls) == 2
    assert client.calls[1]["temperature"] == STRICT_RETRY_TEMPERATURE
    retry_payload = json.loads(client.calls[1]["user_prompt"])
    assert retry_payload["previous_failure"] == "request_payload_echo"


def test_invalid_retry_raises_response_error():
    client = FakeDeepSeekClient(["Hello", "Hello"])
    provider = DeepSeekTextProvider(client)

    with pytest.raises(AIResponseError):
        provider.execute(AITextRequest("Hello", AITextAction.TRANSLATE))

    assert len(client.calls) == 2


def test_long_text_is_chunked_and_merged():
    source = ("alpha " * 55).strip() + "\n\n" + ("beta " * 55).strip()
    client = FakeDeepSeekClient(["甲", "乙"])
    provider = DeepSeekTextProvider(client, chunk_size=400)

    result = provider.execute(AITextRequest(source, AITextAction.TRANSLATE))

    assert result.output_text == "甲\n\n乙"
    assert len(client.calls) == 2
    first_payload = json.loads(client.calls[0]["user_prompt"])
    second_payload = json.loads(client.calls[1]["user_prompt"])
    assert len(first_payload["source_text"]) <= 400
    assert len(second_payload["source_text"]) <= 400


def test_provider_rejects_empty_source_text():
    provider = DeepSeekTextProvider(FakeDeepSeekClient())

    with pytest.raises(AIConfigurationError):
        provider.execute(AITextRequest("   ", AITextAction.TRANSLATE))


def test_provider_rejects_empty_client_output_after_retry():
    provider = DeepSeekTextProvider(FakeDeepSeekClient(["   ", "   "]))

    with pytest.raises(AIResponseError):
        provider.execute(AITextRequest("Hello", AITextAction.TRANSLATE))


def test_provider_close_delegates_to_client():
    client = FakeDeepSeekClient()
    provider = DeepSeekTextProvider(client)

    provider.close()

    assert client.closed is True
