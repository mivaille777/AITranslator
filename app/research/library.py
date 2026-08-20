"""Library-oriented queries layered on the Stage-6 research note store."""

from __future__ import annotations

from contextlib import closing
import sqlite3

from app.research.notes import MAX_RECENT_NOTE_LIMIT, ResearchNote, ResearchNoteStore


LIBRARY_NOTE_LIMIT = MAX_RECENT_NOTE_LIMIT


def _normalized_query(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _clean_note(value: object, *, limit: int = 20_000) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:limit] if len(text) > limit else text


class ResearchNoteLibraryStore(ResearchNoteStore):
    """Add bounded search/detail editing without changing the Stage-6 schema."""

    def get(self, note_id: object) -> ResearchNote | None:
        identifier = str(note_id or "").strip()
        if not identifier:
            return None
        try:
            with closing(self._connect()) as connection:
                self._ensure_schema(connection)
                row = connection.execute(
                    f"SELECT {self._select_columns()} FROM research_notes WHERE note_id = ?",
                    (identifier,),
                ).fetchone()
        except (OSError, sqlite3.Error):
            return None
        return self._row_to_note(row) if row is not None else None

    def search(
        self,
        query: object = "",
        *,
        limit: int = LIBRARY_NOTE_LIMIT,
    ) -> tuple[ResearchNote, ...]:
        notes = self.list_recent(limit=limit)
        needle = _normalized_query(query)
        if not needle:
            return notes
        matched: list[ResearchNote] = []
        for note in notes:
            haystack = _normalized_query(
                "\n".join(
                    (
                        note.resource_title,
                        note.section_heading,
                        note.source_text,
                        note.translated_text,
                        note.ai_content,
                        note.user_note,
                    )
                )
            )
            if needle in haystack:
                matched.append(note)
        return tuple(matched)

    def update_user_note(self, note_id: object, user_note: object) -> ResearchNote | None:
        identifier = str(note_id or "").strip()
        if not identifier:
            return None
        content = _clean_note(user_note)
        try:
            with closing(self._connect()) as connection:
                with connection:
                    self._ensure_schema(connection)
                    cursor = connection.execute(
                        "UPDATE research_notes SET user_note = ?, updated_at = datetime('now') WHERE note_id = ?",
                        (content, identifier),
                    )
                    if not cursor.rowcount:
                        return None
                    row = connection.execute(
                        f"SELECT {self._select_columns()} FROM research_notes WHERE note_id = ?",
                        (identifier,),
                    ).fetchone()
        except (OSError, sqlite3.Error):
            return None
        return self._row_to_note(row) if row is not None else None


__all__ = ["LIBRARY_NOTE_LIMIT", "ResearchNoteLibraryStore"]
