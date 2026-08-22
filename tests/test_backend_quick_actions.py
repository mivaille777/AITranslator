from __future__ import annotations

from fastapi.testclient import TestClient

from app.ai.chat.models import ChatResult
from app.ai.models import AITextAction, AITextResult
from app.research.notes import ResearchNoteStore
from backend.api.dependencies import get_quick_action_service, get_research_note_service
from backend.main import create_app
from backend.services.quick_action_service import QuickActionService
from backend.services.research_note_service import ResearchNoteService


class StubTextService:
    provider_name = "stub-ai"
    model = "stub-model"

    def polish(self, source_text: str, **kwargs) -> AITextResult:
        return AITextResult(
            source_text=source_text,
            output_text=f"polished:{source_text}",
            action=AITextAction.POLISH,
            provider=self.provider_name,
            model=self.model,
            source_language=kwargs.get("source_language", "auto"),
            target_language=kwargs.get("source_language", "auto"),
            style=kwargs.get("style", "academic"),
            request_id=kwargs.get("request_id", 0),
        )

    def close(self) -> None:
        pass


class StubChatService:
    def __init__(self) -> None:
        self.last_request = None

    def execute(self, request):
        self.last_request = request
        return ChatResult(
            session_id=request.session_id,
            user_message=request.user_message,
            output_text="grounded explanation",
            provider="stub-ai",
            model="stub-model",
            request_id=request.request_id,
        )


def _payload(action: str) -> dict[str, object]:
    return {
        "action": action,
        "source_text": "The GP identifies a promising region.",
        "translated_text": "GP 识别一个有希望的区域。",
        "source_language": "en",
        "target_language": "zh-CN",
        "resource_url": "https://example.org/paper",
        "resource_title": "Paper",
        "section_heading": "3. Method",
        "context_before": "Previous sentence.",
        "context_after": "Next sentence.",
        "source_kind": "browser_selection",
        "request_id": 7,
    }


def test_quick_action_service_reuses_chat_reading_context() -> None:
    chat = StubChatService()
    service = QuickActionService(text_service=StubTextService(), chat_service=chat)

    result = service.run(**_payload("reading_explain"))

    assert result.output_text == "grounded explanation"
    assert chat.last_request is not None
    assert chat.last_request.context.reading.section_heading == "3. Method"
    assert chat.last_request.context.reading.context_before == "Previous sentence."
    assert "解释这段内容" in chat.last_request.user_message


def test_quick_action_api_runs_polish_without_chat() -> None:
    app = create_app()
    service = QuickActionService(text_service=StubTextService())
    app.dependency_overrides[get_quick_action_service] = lambda: service

    with TestClient(app) as client:
        response = client.post("/api/quick-actions/run", json=_payload("ai_polish"))

    assert response.status_code == 200
    assert response.json()["output_text"].startswith("polished:")
    assert response.json()["provider"] == "stub-ai"
    assert response.json()["request_id"] == 7


def test_research_note_api_persists_frozen_context(tmp_path) -> None:
    app = create_app()
    store = ResearchNoteStore(storage_path=tmp_path / "notes.sqlite3")
    service = ResearchNoteService(store=store)
    app.dependency_overrides[get_research_note_service] = lambda: service
    payload = _payload("reading_explain")
    payload.pop("action")
    payload.pop("request_id")
    payload["ai_content"] = "AI explanation"
    payload["ai_action"] = "reading_explain"

    with TestClient(app) as client:
        response = client.post("/api/research/notes", json=payload)

    assert response.status_code == 200
    assert response.json()["created"] is True
    notes = store.list_recent(limit=1)
    assert notes[0].resource_title == "Paper"
    assert notes[0].section_heading == "3. Method"
    assert notes[0].ai_content == "AI explanation"
