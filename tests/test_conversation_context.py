from __future__ import annotations

import pytest

from backend.models.companion import CompanionChatRequest
from backend.services.companion_chat_service import CompanionChatService
from backend.services.conversation_lifecycle_service import ConversationLifecycleService


def _reading_kwargs() -> dict[str, object]:
    return {
        "session_id": "context-session",
        "user_message": "Explain this passage.",
        "request_id": 1,
        "source_text": "The GP identifies a statistically promising region.",
        "translated_text": "GP 识别统计上有前景的区域。",
        "source_language": "en",
        "target_language": "zh-CN",
        "resource_url": "https://example.org/paper",
        "resource_title": "A Research Paper",
        "section_heading": "3. Methodology",
        "context_before": "Previous paragraph.",
        "context_after": "Next paragraph.",
        "source_kind": "browser_selection",
    }


def test_general_chat_request_allows_no_reading_context() -> None:
    request = CompanionChatRequest(
        context_mode="general",
        session_id="general-session",
        user_message="Help me plan a refactor.",
    )
    assert request.context_mode == "general"
    assert request.source_text == ""


def test_reading_chat_request_requires_selected_source_text() -> None:
    with pytest.raises(ValueError, match="requires selected source text"):
        CompanionChatRequest(
            context_mode="reading",
            session_id="reading-session",
            user_message="Explain this.",
        )


def test_general_mode_strips_reading_evidence_before_provider_request() -> None:
    request = CompanionChatService._build_request(
        context_mode="general",
        session_id="general-session",
        user_message="Discuss the architecture.",
        source_text="This should not reach the provider as reading evidence.",
        translated_text="不应作为阅读证据传入。",
        resource_title="Private reading context",
        section_heading="Hidden section",
    )
    assert request.context.source_text == ""
    assert request.context.translated_text == ""
    assert request.context.reading.has_context is False


def test_reading_mode_keeps_bounded_evidence_for_provider_request() -> None:
    request = CompanionChatService._build_request(
        context_mode="reading",
        session_id="reading-session",
        user_message="Explain this passage.",
        source_text="Selected evidence.",
        resource_title="Paper",
        section_heading="Method",
    )
    assert request.context.source_text == "Selected evidence."
    assert request.context.reading.resource_title == "Paper"


def test_detach_preserves_reading_context_and_can_reattach(tmp_path) -> None:
    service = ConversationLifecycleService(storage_path=tmp_path / "chat.sqlite3")
    exchange = service.begin_exchange_with_context_mode(
        context_mode="reading",
        **_reading_kwargs(),
    )
    service.finalize_message(exchange.assistant_message_id, status="complete", content="Answer")

    detached = service.update_context(
        exchange.conversation_id,
        context_mode="general",
    )
    assert detached is not None
    assert service.context_mode(exchange.conversation_id) == "general"
    assert detached.source_text.startswith("The GP identifies")

    reattached = service.update_context(
        exchange.conversation_id,
        context_mode="reading",
    )
    assert reattached is not None
    assert service.context_mode(exchange.conversation_id) == "reading"
    assert reattached.resource_title == "A Research Paper"


def test_attach_current_reading_replaces_frozen_context(tmp_path) -> None:
    service = ConversationLifecycleService(storage_path=tmp_path / "chat.sqlite3")
    exchange = service.begin_exchange_with_context_mode(
        context_mode="general",
        session_id="general-session",
        user_message="General question",
        request_id=1,
        source_text="",
    )
    service.finalize_message(exchange.assistant_message_id, status="complete", content="Answer")

    updated = service.update_context(
        exchange.conversation_id,
        context_mode="reading",
        source_text="New selected evidence.",
        translated_text="新的选中证据。",
        resource_title="New Paper",
        section_heading="4. Results",
        source_kind="browser_selection",
    )
    assert updated is not None
    assert service.context_mode(exchange.conversation_id) == "reading"
    assert updated.source_text == "New selected evidence."
    assert updated.resource_title == "New Paper"
