from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import get_research_note_service
from backend.models.quick_actions import (
    ResearchNoteListItem,
    ResearchNoteListResponse,
    ResearchNoteSaveRequest,
    ResearchNoteSaveResponse,
)
from backend.services.research_note_service import ResearchNoteService

router = APIRouter(prefix="/api/research", tags=["research"])
ResearchNoteServiceDependency = Annotated[
    ResearchNoteService,
    Depends(get_research_note_service),
]


@router.get("/notes", response_model=ResearchNoteListResponse)
def list_research_notes(
    service: ResearchNoteServiceDependency,
    limit: int = Query(default=5, ge=1, le=20),
) -> ResearchNoteListResponse:
    notes = service.list_recent(limit=limit)
    return ResearchNoteListResponse(
        total=service.count(),
        notes=[
            ResearchNoteListItem(
                note_id=note.note_id,
                display_title=note.display_title,
                excerpt=note.excerpt,
                updated_at=note.updated_at,
                resource_url=note.resource_url,
                resource_title=note.resource_title,
                section_heading=note.section_heading,
                source_text=note.source_text,
                translated_text=note.translated_text,
                context_before=note.context_before,
                context_after=note.context_after,
                source_kind=note.source_kind,
                ai_content=note.ai_content,
                ai_action=note.ai_action,
            )
            for note in notes
        ],
    )


@router.post("/notes", response_model=ResearchNoteSaveResponse)
def save_research_note(
    payload: ResearchNoteSaveRequest,
    service: ResearchNoteServiceDependency,
) -> ResearchNoteSaveResponse:
    try:
        result = service.save(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    note = result.note
    return ResearchNoteSaveResponse(
        note_id=note.note_id,
        created=result.created,
        display_title=note.display_title,
        excerpt=note.excerpt,
        updated_at=note.updated_at,
    )
