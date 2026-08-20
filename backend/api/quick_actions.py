from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.errors import AIConfigurationError, AIError
from backend.api.dependencies import get_quick_action_service
from backend.models.quick_actions import (
    QuickActionRequest,
    QuickActionResponse,
    QuickActionStatusResponse,
)
from backend.services.quick_action_service import QuickActionService

router = APIRouter(prefix="/api/quick-actions", tags=["quick-actions"])
QuickActionServiceDependency = Annotated[
    QuickActionService,
    Depends(get_quick_action_service),
]


@router.get("/status", response_model=QuickActionStatusResponse)
def quick_action_status(service: QuickActionServiceDependency) -> QuickActionStatusResponse:
    available, provider, model, detail = service.status()
    return QuickActionStatusResponse(
        available=available,
        provider=provider,
        model=model,
        detail=detail,
    )


@router.post("/run", response_model=QuickActionResponse)
def run_quick_action(
    payload: QuickActionRequest,
    service: QuickActionServiceDependency,
) -> QuickActionResponse:
    try:
        result = service.run(**payload.model_dump())
    except AIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return QuickActionResponse(
        action=result.action,
        output_text=result.output_text,
        provider=result.provider,
        model=result.model,
        request_id=result.request_id,
    )
