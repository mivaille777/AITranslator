from fastapi.testclient import TestClient

from backend.api.translation_cascade import get_translation_fallback_service
from backend.main import create_app
from backend.services.translation_fallback_service import (
    TranslationAttempt,
    TranslationCascadeResult,
)


class StubCascadeService:
    def __init__(self) -> None:
        self.last_kwargs = {}

    def translate(self, source_text: str, **kwargs):
        self.last_kwargs = kwargs
        return TranslationCascadeResult(
            source_text=source_text,
            translated_text="译文",
            source_language=kwargs.get("source_language", "auto"),
            target_language=kwargs.get("target_language", "zh-CN"),
            provider="ai",
            model="deepseek-v4-flash",
            request_id=kwargs.get("request_id", 0),
            fallback_level=2 if kwargs.get("provider_mode", "auto") == "auto" else 0,
            notice="有道和 Google 翻译当前不可用，已使用 AI 翻译。"
            if kwargs.get("provider_mode", "auto") == "auto"
            else "",
            attempts=(TranslationAttempt("ai", "success"),),
        )


def test_translation_cascade_api_returns_attempts_and_notice():
    app = create_app()
    service = StubCascadeService()
    app.dependency_overrides[get_translation_fallback_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/translation/cascade",
            json={
                "source_text": "hello",
                "source_language": "en",
                "target_language": "zh-CN",
                "request_id": 9,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["translated_text"] == "译文"
    assert body["provider"] == "ai"
    assert body["model"] == "deepseek-v4-flash"
    assert body["fallback_level"] == 2
    assert body["request_id"] == 9
    assert body["attempts"] == [{"provider": "ai", "status": "success"}]
    assert "有道和 Google 翻译当前不可用" in body["notice"]
    assert service.last_kwargs["provider_mode"] == "auto"


def test_translation_cascade_api_forwards_strict_provider_mode():
    app = create_app()
    service = StubCascadeService()
    app.dependency_overrides[get_translation_fallback_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/translation/cascade",
            json={
                "source_text": "hello",
                "source_language": "en",
                "target_language": "zh-CN",
                "provider_mode": "google_web",
                "request_id": 10,
            },
        )

    assert response.status_code == 200
    assert response.json()["fallback_level"] == 0
    assert service.last_kwargs["provider_mode"] == "google_web"
