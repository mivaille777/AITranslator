from __future__ import annotations

import json
import sqlite3

from app.ai.chat.conversation_manager import ConversationManager, SCHEMA_VERSION
from app.ai.chat.models import ChatContext, ChatRequest, ReadingContext
from app.ai.chat.service import build_chat_prompt


def _reading_context() -> ReadingContext:
    return ReadingContext(
        resource_url="https://example.org/paper",
        resource_title="A Research Paper",
        section_heading="3. Methodology",
        context_before="The statistical model first identifies a promising region.",
        context_after="The language model then refines candidates locally.",
        source_kind="browser_selection",
    )


def test_reading_context_is_encoded_as_reference_data_in_chat_prompt() -> None:
    request = ChatRequest(
        session_id="reading-session",
        user_message="结合上下文解释这句话",
        context=ChatContext(
            source_text="The LLM performs local refinement.",
            translated_text="LLM 执行局部细化。",
            reading=_reading_context(),
        ),
    )

    prompt = build_chat_prompt(request)
    payload = json.loads(prompt.split("\n\n", 1)[1])

    assert payload["selected_context"]["source_text"] == (
        "The LLM performs local refinement."
    )
    assert payload["reading_context"] == {
        "resource_url": "https://example.org/paper",
        "resource_title": "A Research Paper",
        "section_heading": "3. Methodology",
        "context_before": (
            "The statistical model first identifies a promising region."
        ),
        "context_after": "The language model then refines candidates locally.",
        "source_kind": "browser_selection",
    }


def test_reading_context_persists_with_conversation_history(tmp_path) -> None:
    path = tmp_path / "chat_history.sqlite3"
    manager = ConversationManager(storage_path=path)
    conversation = manager.new_conversation(
        context=ChatContext(
            source_text="selected sentence",
            translated_text="选中的句子",
            reading=_reading_context(),
        ),
        provider="deepseek",
        model="deepseek-chat",
    )
    manager.append_exchange("这句话什么意思？", "它描述了局部细化。")

    restored = ConversationManager(storage_path=path)
    active = restored.active

    assert active is not None
    assert active.conversation_id == conversation.conversation_id
    assert active.context.source_text == "selected sentence"
    assert active.context.translated_text == "选中的句子"
    assert active.context.reading == _reading_context()
    assert len(active.messages) == 2


def test_v1_sqlite_schema_is_migrated_in_place_without_losing_messages(tmp_path) -> None:
    path = tmp_path / "legacy_chat_history.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE conversations (
                conversation_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                base_url TEXT NOT NULL DEFAULT '',
                source_text TEXT NOT NULL DEFAULT '',
                translated_text TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                UNIQUE(conversation_id, position)
            );
            """
        )
        connection.execute(
            "INSERT INTO app_state(key, value) VALUES('schema_version', '1')"
        )
        connection.execute(
            "INSERT INTO app_state(key, value) VALUES('active_id', 'legacy')"
        )
        connection.execute(
            """
            INSERT INTO conversations(
                conversation_id, session_id, title, created_at, updated_at,
                provider, model, base_url, source_text, translated_text
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy",
                "legacy-session",
                "旧会话",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
                "deepseek",
                "deepseek-chat",
                "https://api.deepseek.com",
                "old source",
                "旧译文",
            ),
        )
        connection.executemany(
            """
            INSERT INTO messages(conversation_id, position, role, content)
            VALUES(?, ?, ?, ?)
            """,
            [
                ("legacy", 0, "user", "旧问题"),
                ("legacy", 1, "assistant", "旧回答"),
            ],
        )

    manager = ConversationManager(storage_path=path)

    assert manager.active is not None
    assert manager.active.context.source_text == "old source"
    assert manager.active.context.reading == ReadingContext()
    assert [message.content for message in manager.active.messages] == [
        "旧问题",
        "旧回答",
    ]

    with sqlite3.connect(path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(conversations)").fetchall()
        }
        version = connection.execute(
            "SELECT value FROM app_state WHERE key='schema_version'"
        ).fetchone()[0]

    assert {
        "resource_url",
        "resource_title",
        "section_heading",
        "context_before",
        "context_after",
        "context_source_kind",
    }.issubset(columns)
    assert int(version) == SCHEMA_VERSION == 2


def test_active_conversation_context_can_follow_new_reading_without_losing_history(
    tmp_path,
) -> None:
    manager = ConversationManager(storage_path=tmp_path / "chat_history.sqlite3")
    manager.new_conversation(context=ChatContext("first selection", "第一段"))
    manager.append_exchange("解释第一段", "第一段的解释")

    updated = manager.update_active_context(
        ChatContext(
            "second selection",
            "",
            reading=_reading_context(),
        )
    )

    assert len(updated.messages) == 2
    assert updated.context.source_text == "second selection"
    assert updated.context.reading.source_kind == "browser_selection"
