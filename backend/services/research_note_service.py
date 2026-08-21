from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from app.ai.chat.models import ChatContext, ReadingContext
from app.research.notes import ResearchNote, ResearchNoteSaveResult, ResearchNoteStore


@dataclass(frozen=True, slots=True)
class ResearchSourceSummary:
    source_id: str
    display_title: str
    resource_url: str
    source_kind: str
    note_count: int
    linked_conversation_count: int
    updated_at: str


def research_source_id(note: ResearchNote) -> str:
    identity = "\x1f".join(
        (
            note.source_kind.casefold(),
            note.resource_url.casefold(),
            note.resource_title.casefold(),
        )
    )
    if not identity.replace("\x1f", ""):
        identity = f"note:{note.note_id}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


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

    def list_sources(self, *, limit: int = 100) -> tuple[ResearchSourceSummary, ...]:
        notes = self.list_recent(limit=limit)
        grouped: dict[str, dict[str, object]] = {}
        for note in notes:
            source_id = research_source_id(note)
            current = grouped.get(source_id)
            if current is None:
                grouped[source_id] = {
                    "display_title": note.resource_title or note.resource_url or note.source_kind or "Unidentified source",
                    "resource_url": note.resource_url,
                    "source_kind": note.source_kind,
                    "note_count": 1,
                    "conversation_ids": {note.conversation_id} if note.conversation_id else set(),
                    "updated_at": note.updated_at,
                }
                continue
            current["note_count"] = int(current["note_count"]) + 1
            conversation_ids = current["conversation_ids"]
            if isinstance(conversation_ids, set) and note.conversation_id:
                conversation_ids.add(note.conversation_id)
            if note.updated_at > str(current["updated_at"]):
                current["updated_at"] = note.updated_at

        summaries = [
            ResearchSourceSummary(
                source_id=source_id,
                display_title=str(values["display_title"]),
                resource_url=str(values["resource_url"]),
                source_kind=str(values["source_kind"]),
                note_count=int(values["note_count"]),
                linked_conversation_count=len(values["conversation_ids"]),
                updated_at=str(values["updated_at"]),
            )
            for source_id, values in grouped.items()
        ]
        summaries.sort(key=lambda item: item.updated_at, reverse=True)
        return tuple(summaries)


__all__ = [
    "ResearchNoteService",
    "ResearchSourceSummary",
    "research_source_id",
]
