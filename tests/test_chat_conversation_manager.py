from __future__ import annotations

import json
import sqlite3

from app.ai.chat.conversation_manager import ConversationManager
from app.ai.chat.models import ChatContext


def test_conversations_persist_and_restore_recent_active_session(tmp_path) -> None:
    history_path = tmp_path / "chat_history.sqlite3"
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
    manager = ConversationManager(storage_path=tmp_path / "chat_history.sqlite3")
    manager.new_conversation()

    conversation = manager.append_exchange(
        "请详细解释 Gaussian-process-guided statistical localization 为什么适合 PID 调参",
        "回答",
    )

    assert conversation.title != "新对话"
    assert len(conversation.title) <= 36
    assert conversation.title.endswith("…")


def test_sqlite_schema_separates_conversations_and_ordered_messages(tmp_path) -> None:
    history_path = tmp_path / "chat_history.sqlite3"
    manager = ConversationManager(storage_path=history_path)
    conversation = manager.new_conversation(
        context=ChatContext("selected source", "selected translation"),
        provider="deepseek",
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
    )
    manager.append_exchange("first user", "first assistant")
    manager.append_exchange("second user", "second assistant")

    with sqlite3.connect(history_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        row = connection.execute(
            """
            SELECT title, provider, model, source_text, translated_text
            FROM conversations
            WHERE conversation_id = ?
            """,
            (conversation.conversation_id,),
        ).fetchone()
        messages = connection.execute(
            """
            SELECT position, role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY position
            """,
            (conversation.conversation_id,),
        ).fetchall()

    assert {"app_state", "conversations", "messages"}.issubset(tables)
    assert row is not None
    assert row[1:] == (
        "deepseek",
        "deepseek-chat",
        "selected source",
        "selected translation",
    )
    assert messages == [
        (0, "user", "first user"),
        (1, "assistant", "first assistant"),
        (2, "user", "second user"),
        (3, "assistant", "second assistant"),
    ]


def test_database_schema_never_contains_api_key_or_credential_columns(tmp_path) -> None:
    history_path = tmp_path / "chat_history.sqlite3"
    manager = ConversationManager(storage_path=history_path)
    manager.new_conversation(provider="deepseek", model="deepseek-v4-flash")
    manager.append_exchange("hello", "world")

    with sqlite3.connect(history_path) as connection:
        conversation_columns = {
            row[1].lower()
            for row in connection.execute("PRAGMA table_info(conversations)").fetchall()
        }
        message_columns = {
            row[1].lower()
            for row in connection.execute("PRAGMA table_info(messages)").fetchall()
        }

    all_columns = conversation_columns | message_columns
    assert "api_key" not in all_columns
    assert "credential" not in all_columns
    assert "token" not in all_columns


def test_legacy_json_history_is_not_read_or_migrated(tmp_path) -> None:
    legacy_path = tmp_path / "chat_history.json"
    database_path = tmp_path / "chat_history.sqlite3"
    legacy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "active_id": "legacy-id",
                "conversations": [
                    {
                        "conversation_id": "legacy-id",
                        "session_id": "legacy-session",
                        "title": "旧 JSON 会话",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                        "provider": "deepseek",
                        "model": "legacy-model",
                        "base_url": "",
                        "context": {"source_text": "old", "translated_text": "旧"},
                        "messages": [
                            {"role": "user", "content": "legacy question"},
                            {"role": "assistant", "content": "legacy answer"},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = ConversationManager(storage_path=database_path)

    assert database_path.exists()
    assert manager.conversations == ()
    assert manager.active is None

    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    assert count == 0


def test_remove_and_clear_are_persisted_in_sqlite(tmp_path) -> None:
    history_path = tmp_path / "chat_history.sqlite3"
    manager = ConversationManager(storage_path=history_path)
    first = manager.new_conversation()
    manager.append_exchange("first", "reply")
    second = manager.new_conversation()
    manager.append_exchange("second", "reply")

    manager.remove(first.conversation_id)
    manager.clear_active()

    restored = ConversationManager(storage_path=history_path)

    assert [item.conversation_id for item in restored.conversations] == [
        second.conversation_id
    ]
    assert restored.active is not None
    assert restored.active.conversation_id == second.conversation_id
    assert restored.active.title == "新对话"
    assert restored.active.messages == []
