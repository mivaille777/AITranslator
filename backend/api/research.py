from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import get_research_note_service
from backend.models.quick_actions import (
    ResearchNoteListItem,
    ResearchNoteListResponse,
    ResearchNoteSaveRequest,
    ResearchNoteSaveResponse,
)
from backend.models.research import (
    ResearchNoteDeleteResponse,
    ResearchNoteDetailResponse,
    ResearchNoteUpdateRequest,
    ResearchSourceSummaryResponse,
    ResearchWorkspaceResponse,
)
from backend.services.research_note_service import ResearchNoteService, research_source_id

router = APIRouter(prefix="/api/research", tags=["research"])
ResearchNoteServiceDependency = Annotated[
    ResearchNoteService,
    Depends(get_research_note_service),
]


def _detail(note) -> ResearchNoteDetailResponse:
    return ResearchNoteDetailResponse(
        note_id=note.note_id,
        source_id=research_source_id(note),
        created_at=note.created_at,
        updated_at=note.updated_at,
        display_title=note.display_title,
        excerpt=note.excerpt,
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
        user_note=note.user_note,
        conversation_id=note.conversation_id,
    )


@router.get("/workspace", response_model=ResearchWorkspaceResponse)
def research_workspace(
    service: ResearchNoteServiceDependency,
    limit: int = Query(default=100, ge=1, le=100),
) -> ResearchWorkspaceResponse:
    notes = service.list_recent(limit=limit)
    sources = service.list_sources(limit=limit)
    return ResearchWorkspaceResponse(
        total=service.count(),
        sources=[
            ResearchSourceSummaryResponse(
                source_id=item.source_id,
                display_title=item.display_title,
                resource_url=item.resource_url,
                source_kind=item.source_kind,
                note_count=item.note_count,
                linked_conversation_count=item.linked_conversation_count,
                updated_at=item.updated_at,
            )
            for item in sources
        ],
        notes=[_detail(note) for note in notes],
    )


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
                conversation_id=note.conversation_id,
            )
            for note in notes
        ],
    )


@router.get("/notes/{note_id}", response_model=ResearchNoteDetailResponse)
def get_research_note(
    note_id: str,
    service: ResearchNoteServiceDependency,
) -> ResearchNoteDetailResponse:
    note = service.get(note_id)
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research note not found.",
        )
    return _detail(note)


@router.patch("/notes/{note_id}", response_model=ResearchNoteDetailResponse)
def update_research_note(
    note_id: str,
    payload: ResearchNoteUpdateRequest,
    service: ResearchNoteServiceDependency,
) -> ResearchNoteDetailResponse:
    try:
        note = service.update_user_note(note_id, payload.user_note)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research note not found.",
        )
    return _detail(note)


@router.delete("/notes/{note_id}", response_model=ResearchNoteDeleteResponse)
def delete_research_note(
    note_id: str,
    service: ResearchNoteServiceDependency,
) -> ResearchNoteDeleteResponse:
    return ResearchNoteDeleteResponse(
        deleted=service.delete(note_id),
        note_id=note_id,
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
        conversation_id=note.conversation_id,
    )
