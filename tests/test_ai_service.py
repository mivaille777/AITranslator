"""Tests for the provider-independent AI text service."""

from __future__ import annotations

import pytest

from app.ai.errors import AIConfigurationError, AIResponseError
from app.ai.models import AITextAction, AITextRequest, AITextResult
from app.ai.service import AITextService


class FakeProvider:
    name = "fake-ai"
    model = "fake-model"

    def __init__(self) -> None:
        self.requests: list[AITextRequest] = []
        self.closed = False

    def execute(self, request: AITextRequest) -> AITextResult:
        self.requests.append(request)
        return AITextResult(
            source_text="provider-overwrite",
            output_text=f" result:{request.source_text} ",
            action=AITextAction.POLISH,
            provider=self.name,
            model=self.model,
            source_language="wrong",
            target_language="wrong",
            style="wrong",
            request_id=-1,
        )

    def close(self) -> None:
        self.closed = True


class ExplodingProvider:
    def execute(self, _request: AITextRequest) -> AITextResult:
        raise RuntimeError("provider internals must not escape the service")


def test_execute_normalizes_provider_result_metadata() -> None:
    provider = FakeProvider()
    service = AITextService(provider=provider)
    request = AITextRequest(
        source_text="hello",
        action=AITextAction.TRANSLATE,
        source_language="en",
        target_language="zh-CN",
        request_id=17,
    )

    result = service.execute(request)

    assert provider.requests == [request]
    assert result.output_text == "result:hello"
    assert result.source_text == "hello"
    assert result.action is AITextAction.TRANSLATE
    assert result.source_language == "en"
    assert result.target_language == "zh-CN"
    assert result.request_id == 17
    assert result.provider == "fake-ai"
    assert result.model == "fake-model"


def test_translate_and_polish_build_expected_requests() -> None:
    provider = FakeProvider()
    service = AITextService(provider=provider)

    service.translate("hello", source_language="en", target_language="zh-CN", request_id=2)
    service.polish("draft", source_language="en", style="academic", request_id=3)

    translate_request, polish_request = provider.requests
    assert translate_request.action is AITextAction.TRANSLATE
    assert translate_request.target_language == "zh-CN"
    assert translate_request.request_id == 2
    assert polish_request.action is AITextAction.POLISH
    assert polish_request.target_language == "en"
    assert polish_request.style == "academic"
    assert polish_request.request_id == 3


def test_invalid_request_is_rejected_before_provider_call() -> None:
    provider = FakeProvider()
    service = AITextService(provider=provider)

    with pytest.raises(AIConfigurationError):
        service.execute(AITextRequest(source_text="   ", action=AITextAction.TRANSLATE))

    assert provider.requests == []


def test_unexpected_provider_exception_is_converted() -> None:
    service = AITextService(provider=ExplodingProvider())

    with pytest.raises(AIResponseError) as exc_info:
        service.translate("hello")

    assert "provider internals" not in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_service_rejects_unsupported_result() -> None:
    provider = FakeProvider()
    service = AITextService(provider=provider)
    provider.execute = lambda _request: object()  # type: ignore[method-assign]

    with pytest.raises(AIResponseError):
        service.translate("hello")


def test_service_close_releases_provider() -> None:
    provider = FakeProvider()
    service = AITextService(provider=provider)

    service.close()

    assert provider.closed is True
