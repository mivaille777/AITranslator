"""Offline translation provider and manager tests."""

from __future__ import annotations

import pytest

from app.models.translation import TranslationRequest, TranslationResult
from app.translation.errors import TextNormalizationError, TranslationError
from app.translation.fake_provider import FakeTranslationProvider
from app.translation.manager import TranslationManager


def test_translation_manager_success_with_fake_provider() -> None:
    manager = TranslationManager(provider=FakeTranslationProvider())

    result = manager.translate("hello")

    assert result.source_text == "hello"
    assert result.translated_text == "[TEST TRANSLATION] hello"
    assert result.text == result.translated_text
    assert result.source_language == "auto"
    assert result.target_language == "zh-CN"
    assert result.provider == "fake"
    assert result.request_id == 0


def test_translation_manager_preserves_request_id() -> None:
    manager = TranslationManager(provider=FakeTranslationProvider())

    result = manager.translate("hello", request_id=17)

    assert result.request_id == 17


def test_translation_manager_passes_languages_to_provider() -> None:
    provider = FakeTranslationProvider()
    manager = TranslationManager(provider=provider)

    result = manager.translate(
        "hello",
        source_language="en",
        target_language="de",
    )

    assert result.source_language == "en"
    assert result.target_language == "de"


def test_translation_manager_sends_only_normalized_text_to_provider() -> None:
    manager = TranslationManager(provider=FakeTranslationProvider())

    result = manager.translate("  hello\r\n\tworld  ")

    assert result.source_text == "hello\nworld"
    assert result.translated_text == "[TEST TRANSLATION] hello\nworld"


def test_translation_manager_rejects_text_over_configured_limit() -> None:
    manager = TranslationManager(
        provider=FakeTranslationProvider(),
        max_text_length=5,
    )

    with pytest.raises(TextNormalizationError, match="maximum length of 5"):
        manager.translate("123456")


def test_translation_manager_uses_lazy_web_provider_by_default() -> None:
    manager = TranslationManager()

    assert manager.provider.name == "google_web"


def test_translation_manager_rejects_empty_source() -> None:
    class UnexpectedProvider:
        def translate(self, _request):
            raise AssertionError("provider must not be called")

    manager = TranslationManager(provider=UnexpectedProvider())

    with pytest.raises(TranslationError, match="source text is empty"):
        manager.translate("  \n")


def test_translation_manager_wraps_provider_error() -> None:
    class ErrorProvider:
        def translate(self, _request):
            raise RuntimeError("offline")

    manager = TranslationManager(provider=ErrorProvider())

    with pytest.raises(TranslationError, match="provider failed"):
        manager.translate("hello")


def test_translation_manager_rejects_unsupported_result() -> None:
    class UnsupportedProvider:
        def translate(self, _request):
            return {"translatedText": "hello"}

    manager = TranslationManager(provider=UnsupportedProvider())

    with pytest.raises(TranslationError, match="unsupported"):
        manager.translate("hello")


def test_translation_manager_rejects_empty_result() -> None:
    class EmptyProvider:
        def translate(self, request):
            return TranslationResult(
                source_text=request.source_text,
                translated_text="",
            )

    manager = TranslationManager(provider=EmptyProvider())

    with pytest.raises(TranslationError, match="translated text is empty"):
        manager.translate("hello")

