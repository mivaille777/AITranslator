from fastapi.testclient import TestClient

from backend.api.translation_cascade import get_translation_fallback_service
from backend.main import create_app
from backend.services.translation_fallback_service import (
    TranslationAttempt,
    TranslationCascadeResult,
)


class StubCascadeService:
    def translate(self, source_text: str, **kwargs):
        return TranslationCascadeResult(
            source_text=source_text,
            translated_text="译文",
            source_language=kwargs.get("source_language", "auto"),
            target_language=kwargs.get("target_language", "zh-CN"),
            provider="ai",
            model="deepseek-v4-flash",
            request_id=kwargs.get("request_id", 0),
            fallback_level=2,
            notice="有道和 Google 翻译当前不可用，已使用 AI 翻译。",
            attempts=(
                TranslationAttempt("youdao_web", "unavailable"),
                TranslationAttempt("google_web", "unavailable"),
                TranslationAttempt("ai", "success"),
            ),
        )


def test_translation_cascade_api_returns_attempts_and_notice():
    app = create_app()
    app.dependency_overrides[get_translation_fallback_service] = lambda: StubCascadeService()

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
    assert body["attempts"] == [
        {"provider": "youdao_web", "status": "unavailable"},
        {"provider": "google_web", "status": "unavailable"},
        {"provider": "ai", "status": "success"},
    ]
    assert "有道和 Google 翻译当前不可用" in body["notice"]
