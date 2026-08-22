from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_reading_selection_resolver
from backend.models.reading import ReadingSelectionEnvelope, ReadingSelectionResponse
from backend.services.reading_selection_resolver import ReadingSelectionResolver

router = APIRouter(prefix="/api/reading", tags=["reading"])
ReadingSelectionResolverDependency = Annotated[
    ReadingSelectionResolver,
    Depends(get_reading_selection_resolver),
]


@router.get("/selection", response_model=ReadingSelectionEnvelope)
def reading_selection(
    resolver: ReadingSelectionResolverDependency,
) -> ReadingSelectionEnvelope:
    resolved = resolver.resolve()
    if resolved is None:
        return ReadingSelectionEnvelope(selection=None)

    selection = resolved.selection
    document = selection.document
    return ReadingSelectionEnvelope(
        selection=ReadingSelectionResponse(
            selection_id=resolved.selection_id,
            text=selection.text,
            provider=selection.provider,
            source_kind=document.source_kind,
            resource_url=document.resource_url,
            resource_title=document.resource_title,
            local_locator=document.local_locator,
            application=document.application,
            page_number=document.page_number,
            section_heading=selection.section_heading,
            context_before=selection.context_before,
            context_after=selection.context_after,
        )
    )


__all__ = ["router"]
