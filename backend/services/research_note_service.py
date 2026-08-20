from __future__ import annotations

from typing import Any

from app.ai.chat.models import ChatContext, ReadingContext
from app.research.notes import ResearchNoteSaveResult, ResearchNoteStore


class ResearchNoteService:
    """Application boundary around the existing SQLite research-note store."""

    def __init__(self, store: ResearchNoteStore | Any | None = None) -> None:
        self._store = store or ResearchNoteStore()

    def save(
        self,
        *,
        source_text: str,
        translated_text: str = "",
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
