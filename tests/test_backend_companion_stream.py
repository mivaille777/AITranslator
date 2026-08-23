from __future__ import annotations

from time import sleep

from fastapi.testclient import TestClient

from backend.api.dependencies import (
    get_companion_chat_service,
    get_conversation_store_service,
)
from backend.main import create_app
from backend.services.conversation_store_service import ConversationStoreService


def _payload(*, request_id: int = 11, conversation_id: str = "") -> dict[str, object]:
    return {
        "conversation_id": conversation_id,
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


def test_companion_websocket_streams_and_commits_completed_exchange(tmp_path) -> None:
    app = create_app()
    store = ConversationStoreService(storage_path=tmp_path / "chat.sqlite3")
    app.dependency_overrides[get_companion_chat_service] = (
        lambda: StubStreamingCompanionChatService()
    )
    app.dependency_overrides[get_conversation_store_service] = lambda: store

    with TestClient(app) as client:
        with client.websocket_connect("/ws/companion/chat") as websocket:
            websocket.send_json({"type": "start", "request": _payload()})
            accepted = websocket.receive_json()
            first = websocket.receive_json()
            second = websocket.receive_json()
            done = websocket.receive_json()

    conversation_id = accepted["conversation_id"]
    assert accepted["type"] == "accepted"
    assert accepted["request_id"] == 11
    assert conversation_id
    assert accepted["message_id"]
    assert accepted["user_message_id"]
    assert first == {
        "type": "delta",
        "request_id": 11,
        "conversation_id": conversation_id,
        "message_id": accepted["message_id"],
        "delta": "GP anchors ",
        "accumulated_text": "GP anchors ",
    }
    assert second["accumulated_text"] == "GP anchors localize the search."
    assert done["type"] == "done"
    assert done["output_text"] == "GP anchors localize the search."
    assert done["provider"] == "stub-ai"
    assert done["model"] == "stub-model"
    assert done["knowledge_enabled"] is False
    assert done["evidence"] == []
    assert done["citations"] == []

    stored = store.get(conversation_id)
    assert stored is not None
    assert [message.status for message in stored.messages] == ["complete", "complete"]
    assert stored.messages[-1].content == "GP anchors localize the search."


def test_companion_websocket_cancel_commits_terminal_cancelled_message(tmp_path) -> None:
    app = create_app()
    store = ConversationStoreService(storage_path=tmp_path / "chat.sqlite3")
    app.dependency_overrides[get_companion_chat_service] = (
        lambda: SlowStreamingCompanionChatService()
    )
    app.dependency_overrides[get_conversation_store_service] = lambda: store

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
        "conversation_id": accepted["conversation_id"],
        "message_id": accepted["message_id"],
    }
    stored = store.get(accepted["conversation_id"])
    assert stored is not None
    assert stored.messages[-1].status == "cancelled"
    assert stored.messages[-1].error_code == "user_cancelled"
