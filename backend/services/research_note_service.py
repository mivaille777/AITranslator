from __future__ import annotations

from typing import Any

from app.ai.chat.models import ChatContext, ReadingContext
from app.research.notes import ResearchNote, ResearchNoteSaveResult, ResearchNoteStore
from backend.services.research_source_profile import (
    ResearchSourceProfile,
    ResearchSourceSummary,
    research_source_id,
    summarize_source,
)


class ResearchNoteService:
    """Application boundary around the existing SQLite research-note store."""

    def __init__(self, store: ResearchNoteStore | Any | None = None) -> None:
        self._store = store or ResearchNoteStore()

    def save(
        self,
        *,
        source_text: str,
        translated_text: str = "",
        source_language: str = "auto",
        target_language: str = "zh-CN",
        resource_url: str = "",
        resource_title: str = "",
        section_heading: str = "",
        context_before: str = "",
        context_after: str = "",
        source_kind: str = "browser_selection",
        ai_content: str = "",
        ai_action: str = "",
        user_note: str = "",
        conversation_id: str = "",
    ) -> ResearchNoteSaveResult:
        # Language fields are part of the shared reading-context HTTP contract.
        # ResearchNoteStore does not persist them independently because the
        # selected source/translation already carry the relevant language data.
        _ = (source_language, target_language)
        context = ChatContext(
            source_text=source_text,
            translated_text=translated_text,
            reading=ReadingContext(
                resource_url=resource_url,
                resource_title=resource_title,
                section_heading=section_heading,
                context_before=context_before,
                context_after=context_after,
                source_kind=source_kind,
            ),
        )
        return self._store.save_context(
            context,
            ai_content=ai_content,
            ai_action=ai_action,
            user_note=user_note,
            conversation_id=conversation_id,
        )

    def list_recent(self, *, limit: int = 5) -> tuple[ResearchNote, ...]:
        return tuple(self._store.list_recent(limit=limit))

    def get(self, note_id: str) -> ResearchNote | None:
        getter = getattr(self._store, "get", None)
        if not callable(getter):
            return None
        return getter(note_id)

    def update_user_note(self, note_id: str, user_note: str) -> ResearchNote | None:
        updater = getattr(self._store, "update_user_note", None)
        if not callable(updater):
            raise RuntimeError("Research note editing is unavailable.")
        return updater(note_id, user_note)

    def delete(self, note_id: str) -> bool:
        return bool(self._store.delete(note_id))

    def count(self) -> int:
        return int(self._store.count())

    def _group_source_notes(self, *, limit: int = 100) -> dict[str, tuple[ResearchNote, ...]]:
        grouped: dict[str, list[ResearchNote]] = {}
        for note in self.list_recent(limit=limit):
            grouped.setdefault(research_source_id(note), []).append(note)
        return {source_id: tuple(notes) for source_id, notes in grouped.items()}

    def list_sources(self, *, limit: int = 100) -> tuple[ResearchSourceSummary, ...]:
        profiles = [
            summarize_source(notes)
            for notes in self._group_source_notes(limit=limit).values()
        ]
        profiles.sort(key=lambda item: item.updated_at, reverse=True)
        return tuple(
            ResearchSourceSummary(
                source_id=item.source_id,
                display_title=item.display_title,
                resource_url=item.resource_url,
                resource_locator=item.resource_locator,
                source_kind=item.source_kind,
                source_family=item.source_family,
                identity_quality=item.identity_quality,
                note_count=item.note_count,
                section_count=item.section_count,
                linked_conversation_count=item.linked_conversation_count,
                annotation_count=item.annotation_count,
                ai_evidence_count=item.ai_evidence_count,
                updated_at=item.updated_at,
            )
            for item in profiles
        )

    def get_source(self, source_id: str, *, limit: int = 100) -> ResearchSourceProfile | None:
        candidate = str(source_id or "").strip()
        if not candidate:
            return None
        notes = self._group_source_notes(limit=limit).get(candidate)
        if not notes:
            return None
        return summarize_source(notes)


__all__ = [
    "ResearchNoteService",
    "ResearchSourceProfile",
    "ResearchSourceSummary",
    "research_source_id",
]
