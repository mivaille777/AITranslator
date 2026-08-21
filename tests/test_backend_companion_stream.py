from __future__ import annotations

from time import sleep

from fastapi.testclient import TestClient

from backend.api.dependencies import get_companion_chat_service
from backend.main import create_app


def _payload(*, request_id: int = 11) -> dict[str, object]:
    return {
        "session_id": "companion-stream-1",
        "user_message": "Explain why the GP anchor helps.",
        "source_text": "The LLM performs local refinement around the GP anchor.",
        "translated_text": "LLM 围绕 GP 锚点执行局部细化。",
        "source_language": "en",
        "target_language": "zh-CN",
        "resource_url": "https://example.org/paper",
        "resource_title": "A Research Paper",
        "section_heading": "3. Methodology",
        "context_before": "The GP identifies a statistically promising region.",
        "context_after": "The candidate is validated deterministically.",
        "source_kind": "browser_selection",
        "history": [],
        "request_id": request_id,
    }


class StubStreamingCompanionChatService:
    provider_name = "stub-ai"
    model = "stub-model"

    def stream(self, **_kwargs):
        yield "GP anchors "
        yield "localize the search."


class SlowStreamingCompanionChatService:
    provider_name = "stub-ai"
    model = "stub-model"

    def stream(self, **_kwargs):
        for part in ("one", "two", "three"):
            sleep(0.05)
            yield part


def test_companion_websocket_streams_ordered_deltas_and_done_event() -> None:
    app = create_app()
    app.dependency_overrides[get_companion_chat_service] = (
        lambda: StubStreamingCompanionChatService()
    )

    with TestClient(app) as client:
        with client.websocket_connect("/ws/companion/chat") as websocket:
            websocket.send_json({"type": "start", "request": _payload()})
            accepted = websocket.receive_json()
            first = websocket.receive_json()
            second = websocket.receive_json()
            done = websocket.receive_json()

    assert accepted["type"] == "accepted"
    assert accepted["request_id"] == 11
    assert accepted["conversation_id"] == "companion-stream-1"
    assert accepted["message_id"]
    assert first == {
        "type": "delta",
        "request_id": 11,
        "conversation_id": "companion-stream-1",
        "message_id": accepted["message_id"],
        "delta": "GP anchors ",
        "accumulated_text": "GP anchors ",
    }
    assert second["accumulated_text"] == "GP anchors localize the search."
    assert done["type"] == "done"
    assert done["output_text"] == "GP anchors localize the search."
    assert done["provider"] == "stub-ai"
    assert done["model"] == "stub-model"


def test_companion_websocket_cancel_emits_terminal_cancelled_event() -> None:
    app = create_app()
    app.dependency_overrides[get_companion_chat_service] = (
        lambda: SlowStreamingCompanionChatService()
    )

    with TestClient(app) as client:
        with client.websocket_connect("/ws/companion/chat") as websocket:
            websocket.send_json({"type": "start", "request": _payload(request_id=22)})
            accepted = websocket.receive_json()
            websocket.send_json({"type": "cancel", "request_id": 22})
            terminal = websocket.receive_json()

    assert accepted["type"] == "accepted"
    assert terminal == {
        "type": "cancelled",
        "request_id": 22,
        "conversation_id": "companion-stream-1",
        "message_id": accepted["message_id"],
    }
