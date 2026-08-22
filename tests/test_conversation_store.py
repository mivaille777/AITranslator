from __future__ import annotations

from backend.services.conversation_store_service import ConversationStoreService


def _begin(service: ConversationStoreService, *, request_id: int = 1):
    return service.begin_exchange(
        session_id="session-1",
        user_message="Why does the GP anchor help?",
        request_id=request_id,
        source_text="The LLM refines around the GP anchor.",
        translated_text="LLM 围绕 GP 锚点细化。",
        source_language="en",
        target_language="zh-CN",
        resource_url="https://example.org/paper",
        resource_title="Paper",
        section_heading="3. Method",
        context_before="Before",
        context_after="After",
        source_kind="browser_selection",
    )


def test_conversation_store_commits_stream_lifecycle_and_restores_messages(tmp_path) -> None:
    path = tmp_path / "chat.sqlite3"
    service = ConversationStoreService(storage_path=path)
    exchange = _begin(service)

    service.update_stream(exchange.assistant_message_id, "GP anchors ")
    service.finalize_message(
        exchange.assistant_message_id,
        status="complete",
        content="GP anchors localize the search.",
        provider="stub-ai",
        model="stub-model",
    )

    restored = ConversationStoreService(storage_path=path).get(exchange.conversation_id)

    assert restored is not None
    assert restored.title.startswith("Why does the GP anchor")
    assert [message.role for message in restored.messages] == ["user", "assistant"]
    assert restored.messages[0].status == "complete"
    assert restored.messages[1].status == "complete"
    assert restored.messages[1].content == "GP anchors localize the search."
    assert restored.messages[1].provider == "stub-ai"
    assert restored.messages[1].model == "stub-model"


def test_conversation_store_recovers_interrupted_stream_as_cancelled(tmp_path) -> None:
    path = tmp_path / "chat.sqlite3"
    service = ConversationStoreService(storage_path=path)
    exchange = _begin(service, request_id=9)
    service.update_stream(exchange.assistant_message_id, "partial answer")

    recovered = ConversationStoreService(storage_path=path).get(exchange.conversation_id)

    assert recovered is not None
    assistant = recovered.messages[-1]
    assert assistant.status == "cancelled"
    assert assistant.error_code == "interrupted"
    assert assistant.content == "partial answer"


def test_conversation_store_rename_delete_and_continue_existing_conversation(tmp_path) -> None:
    service = ConversationStoreService(storage_path=tmp_path / "chat.sqlite3")
    first = _begin(service)
    service.finalize_message(first.assistant_message_id, status="cancelled")

    second = service.begin_exchange(
        conversation_id=first.conversation_id,
        session_id="session-1",
        user_message="Continue.",
        request_id=2,
        source_text="ignored for existing conversation",
    )
    service.finalize_message(second.assistant_message_id, status="complete", content="Done")

    renamed = service.rename(first.conversation_id, "GP refinement discussion")
    assert renamed is not None
    assert renamed.title == "GP refinement discussion"
    assert len(renamed.messages) == 4
    assert service.list_recent(limit=5)[0].conversation_id == first.conversation_id

    assert service.delete(first.conversation_id) is True
    assert service.get(first.conversation_id) is None
