from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_browser_context_service
from backend.models.browser_context import (
    BrowserBridgeStatusResponse,
    BrowserPageEnvelope,
    BrowserPageResponse,
    BrowserSelectionEnvelope,
    BrowserSelectionResponse,
)
from backend.services.browser_context_service import BrowserContextService

router = APIRouter(prefix="/api/browser", tags=["browser"])
BrowserContextServiceDependency = Annotated[
    BrowserContextService,
    Depends(get_browser_context_service),
]


@router.get("/status", response_model=BrowserBridgeStatusResponse)
def browser_status(
    service: BrowserContextServiceDependency,
) -> BrowserBridgeStatusResponse:
    status = service.status()
    return BrowserBridgeStatusResponse(
        running=status.running,
        host=status.host,
        port=status.port,
        endpoint=status.endpoint,
        has_extension_activity=status.has_extension_activity,
        last_activity_age_seconds=status.last_activity_age_seconds,
        last_title=status.last_title,
        last_url=status.last_url,
        last_heading=status.last_heading,
    )


@router.get("/selection", response_model=BrowserSelectionEnvelope)
def browser_selection(
    service: BrowserContextServiceDependency,
) -> BrowserSelectionEnvelope:
    snapshot = service.latest_selection()
    if snapshot is None:
        return BrowserSelectionEnvelope(selection=None)
    return BrowserSelectionEnvelope(
        selection=BrowserSelectionResponse(
            selection_id=f"{snapshot.received_at:.9f}",
            text=snapshot.text,
            url=snapshot.url,
            title=snapshot.title,
            heading=snapshot.heading,
            context_before=snapshot.context_before,
            context_after=snapshot.context_after,
            frame_url=snapshot.frame_url,
            top_level=snapshot.top_level,
            captured_at_ms=snapshot.browser_captured_at_ms,
        )
    )


@router.get("/page", response_model=BrowserPageEnvelope)
def browser_page(
    service: BrowserContextServiceDependency,
) -> BrowserPageEnvelope:
    snapshot = service.latest_page()
    if snapshot is None:
        return BrowserPageEnvelope(page=None)
    return BrowserPageEnvelope(
        page=BrowserPageResponse(
            page_id=f"{snapshot.received_at:.9f}",
            url=snapshot.url,
            title=snapshot.title,
            heading=snapshot.heading,
            frame_url=snapshot.frame_url,
        )
    )
