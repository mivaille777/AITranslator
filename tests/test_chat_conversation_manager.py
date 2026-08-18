from __future__ import annotations

from app.ai.chat.conversation_manager import ConversationManager
from app.ai.chat.models import ChatContext


def test_conversations_persist_and_restore_recent_active_session(tmp_path) -> None:
    history_path = tmp_path / "chat_history.json"
    manager = ConversationManager(storage_path=history_path)
    first = manager.new_conversation(
        context=ChatContext("source paragraph", "译文"),
        provider="deepseek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    manager.append_exchange("为什么使用 GP？", "因为它提供统计定位。")
    second = manager.new_conversation(
        provider="deepseek",
        model="deepseek-v4-pro",
        base_url="https://api.deepseek.com",
    )
    manager.append_exchange("第二个问题", "第二个回答")
    manager.switch(first.conversation_id)

    restored = ConversationManager(storage_path=history_path)

    assert restored.active is not None
    assert restored.active.conversation_id == first.conversation_id
    assert restored.active.title == "为什么使用 GP？"
    assert len(restored.active.messages) == 2
    assert {item.conversation_id for item in restored.conversations} == {
        first.conversation_id,
        second.conversation_id,
    }


def test_first_user_turn_becomes_compact_conversation_title(tmp_path) -> None:
    manager = ConversationManager(storage_path=tmp_path / "chat_history.json")
    manager.new_conversation()

    conversation = manager.append_exchange(
        "请详细解释 Gaussian-process-guided statistical localization 为什么适合 PID 调参",
        "回答",
    )

    assert conversation.title != "新对话"
    assert len(conversation.title) <= 36
    assert conversation.title.endswith("…")


def test_history_file_never_contains_api_key_field(tmp_path) -> None:
    history_path = tmp_path / "chat_history.json"
    manager = ConversationManager(storage_path=history_path)
    manager.new_conversation(provider="deepseek", model="deepseek-v4-flash")
    manager.append_exchange("hello", "world")

    content = history_path.read_text(encoding="utf-8")

    assert "api_key" not in content.lower()
    assert "credential" not in content.lower()
