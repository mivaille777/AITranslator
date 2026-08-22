from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_conversation_store_service
from backend.main import create_app
from backend.services.conversation_lifecycle_service import ConversationLifecycleService


def _begin(service: ConversationLifecycleService, *, conversation_id: str = "", message: str, request_id: int):
    return service.begin_exchange(
        conversation_id=conversation_id,
        session_id="session-1",
        user_message=message,
        request_id=request_id,
        source_text="Selected research passage",
        translated_text="选中的研究段落",
        source_language="en",
        target_language="zh-CN",
        resource_url="https://example.org/paper",
        resource_title="Paper",
        section_heading="3. Method",
        context_before="Before",
        context_after="After",
        source_kind="browser_selection",
    )


def test_rewind_removes_target_user_message_and_later_branch(tmp_path) -> None:
    service = ConversationLifecycleService(storage_path=tmp_path / "chat.sqlite3")
    first = _begin(service, message="First question", request_id=1)
    service.finalize_message(first.assistant_message_id, status="complete", content="First answer")
    second = _begin(
        service,
        conversation_id=first.conversation_id,
        message="Second question",
        request_id=2,
    )
    service.finalize_message(second.assistant_message_id, status="complete", content="Second answer")

    rewound = service.rewind_from_user_message(first.conversation_id, second.user_message_id)

    assert rewound is not None
    assert [message.content for message in rewound.messages] == ["First question", "First answer"]


def test_editing_first_message_rebuilds_auto_title_on_next_exchange(tmp_path) -> None:
    service = ConversationLifecycleService(storage_path=tmp_path / "chat.sqlite3")
    first = _begin(service, message="Original question", request_id=1)
    service.finalize_message(first.assistant_message_id, status="complete", content="Answer")

    rewound = service.rewind_from_user_message(first.conversation_id, first.user_message_id)
    assert rewound is not None
    assert rewound.messages == ()
    assert rewound.title == "New conversation"

    replacement = _begin(
        service,
        conversation_id=first.conversation_id,
        message="Edited question",
        request_id=2,
    )
    service.finalize_message(replacement.assistant_message_id, status="complete", content="New answer")
    restored = service.get(first.conversation_id)

    assert restored is not None
    assert restored.title == "Edited question"
    assert [message.content for message in restored.messages] == ["Edited question", "New answer"]


def test_rewind_is_rejected_while_generation_is_streaming(tmp_path) -> None:
    service = ConversationLifecycleService(storage_path=tmp_path / "chat.sqlite3")
    exchange = _begin(service, message="Question", request_id=1)

    with pytest.raises(ValueError, match="generation is active"):
        service.rewind_from_user_message(exchange.conversation_id, exchange.user_message_id)


def test_rewind_api_returns_remaining_conversation_branch(tmp_path) -> None:
    service = ConversationLifecycleService(storage_path=tmp_path / "chat.sqlite3")
    first = _begin(service, message="First", request_id=1)
    service.finalize_message(first.assistant_message_id, status="complete", content="One")
    second = _begin(service, conversation_id=first.conversation_id, message="Second", request_id=2)
    service.finalize_message(second.assistant_message_id, status="complete", content="Two")

    app = create_app()
    app.dependency_overrides[get_conversation_store_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            f"/api/conversations/{first.conversation_id}/rewind",
            json={"user_message_id": second.user_message_id},
        )

    assert response.status_code == 200
    assert [item["content"] for item in response.json()["messages"]] == ["First", "One"]
