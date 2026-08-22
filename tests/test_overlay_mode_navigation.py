from fastapi.testclient import TestClient

from backend.api.dependencies import get_overlay_state_service
from backend.main import create_app
from backend.services.overlay_state_service import OverlayStateService


def make_client() -> tuple[TestClient, OverlayStateService]:
    service = OverlayStateService()
    app = create_app()
    app.dependency_overrides[get_overlay_state_service] = lambda: service
    return TestClient(app), service


def test_overlay_mode_api_preserves_cached_translation_and_conversation():
    client, service = make_client()
    service.show_assistant(
        context_id="selection-a",
        source_text="paper text",
        source_language="en",
        target_language="zh-CN",
    )
    service.bind_companion_conversation(
        context_id="selection-a",
        conversation_id="conversation-1",
    )
    service.show_translation(
        context_id="selection-a",
        source_text="paper text",
        translated_text="论文文本",
        source_language="en",
        target_language="zh-CN",
        provider="youdao_web",
    )

    assistant = client.post(
        "/api/overlay/mode",
        json={"context_id": "selection-a", "mode": "assistant"},
    )
    assert assistant.status_code == 200
    assert assistant.json()["mode"] == "assistant"
    assert assistant.json()["translated_text"] == "论文文本"
    assert assistant.json()["companion_conversation_id"] == "conversation-1"

    translation = client.post(
        "/api/overlay/mode",
        json={"context_id": "selection-a", "mode": "translation"},
    )
    assert translation.status_code == 200
    assert translation.json()["mode"] == "translation"
    assert translation.json()["translated_text"] == "论文文本"
    assert translation.json()["provider"] == "youdao_web"


def test_translation_failure_stays_interactive_and_preserves_conversation():
    client, service = make_client()
    service.show_assistant(
        context_id="selection-a",
        source_text="paper text",
        source_language="en",
        target_language="zh-CN",
    )
    service.bind_companion_conversation(
        context_id="selection-a",
        conversation_id="conversation-1",
    )

    response = client.post(
        "/api/overlay/translation-failure",
        json={
            "context_id": "selection-a",
            "source_text": "paper text",
            "source_language": "en",
            "target_language": "zh-CN",
            "message": "all providers unavailable",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "translation"
    assert body["phase"] == "ready"
    assert body["companion_conversation_id"] == "conversation-1"
    assert "all providers unavailable" in body["translation_notice"]


def test_overlay_mode_api_rejects_stale_context():
    client, service = make_client()
    service.show_assistant(
        context_id="selection-current",
        source_text="paper text",
        source_language="en",
        target_language="zh-CN",
    )

    response = client.post(
        "/api/overlay/mode",
        json={"context_id": "selection-stale", "mode": "translation"},
    )

    assert response.status_code == 409
