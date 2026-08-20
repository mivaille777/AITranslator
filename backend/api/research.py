from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import get_research_note_service
from backend.models.quick_actions import ResearchNoteSaveRequest, ResearchNoteSaveResponse
from backend.services.research_note_service import ResearchNoteService

router = APIRouter(prefix="/api/research", tags=["research"])
ResearchNoteServiceDependency = Annotated[
    ResearchNoteService,
    Depends(get_research_note_service),
]


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
