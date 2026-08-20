from fastapi.testclient import TestClient

from app.models.translation import TranslationResult
from app.translation.errors import TextNormalizationError
from backend.api.dependencies import get_translation_service
from backend.main import create_app
from backend.services.translation_service import TranslationService


class StubManager:
    provider_name = "stub_provider"
    default_source_language = "auto"
    default_target_language = "zh-CN"

    def __init__(self) -> None:
        self.closed = False
        self.last_call: tuple[str, str, str, int] | None = None

    def translate(
        self,
        source_text: str,
        source_language: str | None = None,
        target_language: str | None = None,
        request_id: int = 0,
    ) -> TranslationResult:
        self.last_call = (
            source_text,
            source_language or "auto",
            target_language or "zh-CN",
            request_id,
        )
        return TranslationResult(
            source_text=source_text,
            translated_text=f"translated:{source_text}",
            source_language="en",
            target_language=target_language or "zh-CN",
            provider=self.provider_name,
            request_id=request_id,
        )

    def close(self) -> None:
        self.closed = True


class RejectingService:
    provider_name = "stub_provider"
    default_source_language = "auto"
    default_target_language = "zh-CN"

    def translate(self, *args, **kwargs):
        raise TextNormalizationError("source text is empty")


def test_translation_service_delegates_to_existing_manager() -> None:
    manager = StubManager()
    service = TranslationService(manager=manager)  # type: ignore[arg-type]

    result = service.translate(
        "hello",
        source_language="en",
        target_language="zh-CN",
        request_id=7,
    )

    assert result.translated_text == "translated:hello"
    assert manager.last_call == ("hello", "en", "zh-CN", 7)


def test_translation_api_returns_provider_independent_result() -> None:
    app = create_app()
    manager = StubManager()
    service = TranslationService(manager=manager)  # type: ignore[arg-type]
    app.dependency_overrides[get_translation_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/translation",
            json={
                "source_text": "hello",
                "source_language": "en",
                "target_language": "zh-CN",
                "request_id": 12,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "source_text": "hello",
        "translated_text": "translated:hello",
        "source_language": "en",
        "target_language": "zh-CN",
        "provider": "stub_provider",
        "request_id": 12,
    }


def test_translation_status_exposes_current_defaults() -> None:
    app = create_app()
    manager = StubManager()
    service = TranslationService(manager=manager)  # type: ignore[arg-type]
    app.dependency_overrides[get_translation_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/translation/status")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "stub_provider",
        "source_language": "auto",
        "target_language": "zh-CN",
    }


def test_translation_api_maps_normalization_errors_to_422() -> None:
    app = create_app()
    app.dependency_overrides[get_translation_service] = lambda: RejectingService()

    with TestClient(app) as client:
        response = client.post(
            "/api/translation",
            json={"source_text": " ", "source_language": "auto", "target_language": "zh-CN"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "source text is empty"
