from fastapi.testclient import TestClient

from backend.api.dependencies import get_overlay_state_service
from backend.main import app
from backend.services.overlay_state_service import OverlayStateService


def test_overlay_api_tracks_loading_translation_and_dismissal() -> None:
    service = OverlayStateService()
    app.dependency_overrides[get_overlay_state_service] = lambda: service
    try:
        client = TestClient(app)

        initial = client.get("/api/overlay")
        assert initial.status_code == 200
        assert initial.json()["visible"] is False
        assert initial.json()["phase"] == "hidden"

        loading = client.post(
            "/api/overlay/loading",
            json={
                "context_id": "selection-1",
                "source_text": "hello",
                "source_language": "auto",
                "target_language": "zh-CN",
            },
        )
        assert loading.status_code == 200
        assert loading.json()["visible"] is True
        assert loading.json()["phase"] == "loading"

        ready = client.post(
            "/api/overlay/present",
            json={
                "context_id": "selection-1",
                "source_text": "hello",
                "translated_text": "你好",
                "source_language": "en",
                "target_language": "zh-CN",
                "provider": "fake",
            },
        )
        assert ready.status_code == 200
        assert ready.json()["phase"] == "ready"
        assert ready.json()["translated_text"] == "你好"

        dismissed = client.post("/api/overlay/dismiss", json={})
        assert dismissed.status_code == 200
        assert dismissed.json()["visible"] is False
        assert dismissed.json()["phase"] == "hidden"
    finally:
        app.dependency_overrides.pop(get_overlay_state_service, None)


def test_overlay_service_ignores_stale_translation_results() -> None:
    service = OverlayStateService()
    service.show_loading(
        context_id="new-selection",
        source_text="new",
        source_language="auto",
        target_language="zh-CN",
    )

    state = service.show_translation(
        context_id="old-selection",
        source_text="old",
        translated_text="旧",
        source_language="en",
        target_language="zh-CN",
        provider="fake",
    )

    assert state.context_id == "new-selection"
    assert state.phase == "loading"
    assert state.translated_text == ""
