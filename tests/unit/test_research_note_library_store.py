from __future__ import annotations

from app.ai.chat.models import ChatContext, ReadingContext
from app.research.library import ResearchNoteLibraryStore


def _context(title: str, source: str, section: str) -> ChatContext:
    return ChatContext(
        source_text=source,
        translated_text=f"译文：{source}",
        reading=ReadingContext(
            resource_url=f"https://example.org/{title.replace(' ', '-').lower()}",
            resource_title=title,
            section_heading=section,
            source_kind="browser_selection",
        ),
    )


def test_library_search_matches_title_section_and_note_content(tmp_path) -> None:
    store = ResearchNoteLibraryStore(storage_path=tmp_path / "notes.sqlite3")
    first = store.save_context(
        _context("Bayesian Optimization Paper", "GP anchor selection", "3. Method")
    ).note
    second = store.save_context(
        _context("Control Paper", "Safety gate validation", "4. Experiments")
    ).note
    store.update_user_note(second.note_id, "重点关注 actuator constraints")

    assert [note.note_id for note in store.search("Bayesian")] == [first.note_id]
    assert [note.note_id for note in store.search("Experiments")] == [second.note_id]
    assert [note.note_id for note in store.search("actuator constraints")] == [second.note_id]


def test_library_updates_user_note_without_changing_saved_source(tmp_path) -> None:
    store = ResearchNoteLibraryStore(storage_path=tmp_path / "notes.sqlite3")
    saved = store.save_context(
        _context("Research Paper", "Original selected passage", "2. Related Work")
    ).note

    updated = store.update_user_note(saved.note_id, "这是我自己的研究笔记。")

    assert updated is not None
    assert updated.note_id == saved.note_id
    assert updated.source_text == "Original selected passage"
    assert updated.user_note == "这是我自己的研究笔记。"
    assert store.get(saved.note_id) == updated
