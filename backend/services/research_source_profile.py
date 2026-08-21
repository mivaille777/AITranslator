from __future__ import annotations

from dataclasses import dataclass
import hashlib

from app.research.notes import ResearchNote
from app.research.source_identity import (
    ResearchSourceIdentity,
    build_research_source_identity,
)


@dataclass(frozen=True, slots=True)
class ResearchSourceSectionSummary:
    section_id: str
    heading: str
    note_count: int
    linked_conversation_count: int
    annotation_count: int
    ai_evidence_count: int
    updated_at: str


@dataclass(frozen=True, slots=True)
class ResearchSourceSummary:
    source_id: str
    display_title: str
    resource_url: str
    resource_locator: str
    source_kind: str
    source_family: str
    identity_quality: str
    note_count: int
    section_count: int
    linked_conversation_count: int
    annotation_count: int
    ai_evidence_count: int
    updated_at: str


@dataclass(frozen=True, slots=True)
class ResearchSourceProfile(ResearchSourceSummary):
    sections: tuple[ResearchSourceSectionSummary, ...]


def source_identity_for_note(note: ResearchNote) -> ResearchSourceIdentity:
    return build_research_source_identity(
        resource_url=note.resource_url,
        resource_title=note.resource_title,
        source_kind=note.source_kind,
        fallback_key=note.note_id,
    )


def research_source_id(note: ResearchNote) -> str:
    return source_identity_for_note(note).source_id


def _section_heading(note: ResearchNote) -> str:
    return " ".join(note.section_heading.strip().split()) or "Unsectioned evidence"


def _section_id(source_id: str, heading: str) -> str:
    material = f"{source_id}\x1f{heading.casefold()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def summarize_source(notes: tuple[ResearchNote, ...]) -> ResearchSourceProfile:
    if not notes:
        raise ValueError("Research source profile requires at least one note.")

    # list_recent() is newest-first, so this note carries the freshest source metadata.
    representative = notes[0]
    identity = source_identity_for_note(representative)
    conversation_ids = {note.conversation_id for note in notes if note.conversation_id}
    annotation_count = sum(1 for note in notes if note.user_note.strip())
    ai_evidence_count = sum(1 for note in notes if note.ai_content.strip())

    grouped_sections: dict[str, list[ResearchNote]] = {}
    for note in notes:
        grouped_sections.setdefault(_section_heading(note), []).append(note)

    sections: list[ResearchSourceSectionSummary] = []
    for heading, section_notes in grouped_sections.items():
        section_conversations = {
            note.conversation_id for note in section_notes if note.conversation_id
        }
        sections.append(
            ResearchSourceSectionSummary(
                section_id=_section_id(identity.source_id, heading),
                heading=heading,
                note_count=len(section_notes),
                linked_conversation_count=len(section_conversations),
                annotation_count=sum(1 for note in section_notes if note.user_note.strip()),
                ai_evidence_count=sum(1 for note in section_notes if note.ai_content.strip()),
                updated_at=max(note.updated_at for note in section_notes),
            )
        )
    sections.sort(key=lambda item: item.updated_at, reverse=True)

    return ResearchSourceProfile(
        source_id=identity.source_id,
        display_title=identity.display_title,
        resource_url=representative.resource_url,
        resource_locator=identity.resource_locator,
        source_kind=identity.source_kind,
        source_family=identity.source_family,
        identity_quality=identity.identity_quality,
        note_count=len(notes),
        section_count=len(sections),
        linked_conversation_count=len(conversation_ids),
        annotation_count=annotation_count,
        ai_evidence_count=ai_evidence_count,
        updated_at=max(note.updated_at for note in notes),
        sections=tuple(sections),
    )


__all__ = [
    "ResearchSourceProfile",
    "ResearchSourceSectionSummary",
    "ResearchSourceSummary",
    "research_source_id",
    "source_identity_for_note",
    "summarize_source",
]
