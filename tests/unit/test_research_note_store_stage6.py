from __future__ import annotations

import sqlite3

import pytest

from app.ai.chat.models import ChatContext, ReadingContext
from app.research.notes import RESEARCH_NOTES_SCHEMA_VERSION, ResearchNoteStore


def _context(*, translation: str = "") -> ChatContext:
    return ChatContext(
        source_text="The LLM performs local refinement around the GP anchor.",
        translated_text=translation,
        reading=ReadingContext(
            resource_url="https://example.org/paper",
            resource_title="A Research Paper",
            section_heading="3. Methodology",
            context_before="The GP identifies a statistically promising region.",
            context_after="The candidate is validated deterministically.",
            source_kind="browser_selection",
        ),
    )


def test_research_note_store_persists_structured_reading_context(tmp_path) -> None:
    path = tmp_path / "research_notes.sqlite3"
    store = ResearchNoteStore(storage_path=path)

    saved = store.save_context(
        _context(translation="LLM 围绕 GP 锚点执行局部细化。"),
        ai_content="这段说明 GP 负责定位，LLM 负责局部细化。",
        ai_action="reading_explain",
        conversation_id="conversation-1",
    )

    assert saved.created
    assert store.count() == 1

    restored = ResearchNoteStore(storage_path=path).list_recent(limit=5)
    assert len(restored) == 1
    note = restored[0]
    assert note.note_id == saved.note.note_id
    assert note.resource_title == "A Research Paper"
    assert note.section_heading == "3. Methodology"
    assert note.source_kind == "browser_selection"
    assert note.translated_text == "LLM 围绕 GP 锚点执行局部细化。"
    assert note.ai_action == "reading_explain"
    assert "GP 负责定位" in note.ai_content
    assert note.conversation_id == "conversation-1"


def test_same_selection_is_upserted_and_enriched_instead_of_duplicated(tmp_path) -> None:
    store = ResearchNoteStore(storage_path=tmp_path / "research_notes.sqlite3")

    first = store.save_context(_context())
    second = store.save_context(
        _context(translation="局部细化译文"),
        ai_content="AI explanation",
        ai_action="reading_explain",
    )

    assert first.created
    assert not second.created
    assert first.note.note_id == second.note.note_id
    assert store.count() == 1
    assert second.note.translated_text == "局部细化译文"
    assert second.note.ai_content == "AI explanation"
    assert second.note.ai_action == "reading_explain"


def test_later_sparse_save_does_not_erase_existing_enrichment(tmp_path) -> None:
    store = ResearchNoteStore(storage_path=tmp_path / "research_notes.sqlite3")
    enriched = store.save_context(
        _context(translation="已有译文"),
        ai_content="已有 AI 解释",
        ai_action="reading_explain",
    )

    sparse = store.save_context(_context())

    assert sparse.note.note_id == enriched.note.note_id
    assert sparse.note.translated_text == "已有译文"
    assert sparse.note.ai_content == "已有 AI 解释"
    assert sparse.note.ai_action == "reading_explain"


def test_research_note_store_requires_selected_source_text(tmp_path) -> None:
    store = ResearchNoteStore(storage_path=tmp_path / "research_notes.sqlite3")

    with pytest.raises(ValueError):
        store.save_context(ChatContext())


def test_research_note_database_has_explicit_schema_version(tmp_path) -> None:
    path = tmp_path / "research_notes.sqlite3"
    ResearchNoteStore(storage_path=path)

    with sqlite3.connect(path) as connection:
        version = connection.execute(
            "SELECT value FROM app_state WHERE key='schema_version'"
        ).fetchone()[0]
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(research_notes)").fetchall()
        }

    assert int(version) == RESEARCH_NOTES_SCHEMA_VERSION == 1
    assert {
        "resource_url",
        "resource_title",
        "section_heading",
        "source_text",
        "translated_text",
        "ai_content",
        "ai_action",
        "user_note",
        "conversation_id",
    }.issubset(columns)
