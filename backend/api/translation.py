from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.translation.errors import TextNormalizationError, TranslationError
from backend.api.dependencies import get_translation_service
from backend.models.translation import (
    TranslationApiRequest,
    TranslationApiResponse,
    TranslationStatusResponse,
)
from backend.services.translation_service import TranslationService

router = APIRouter(prefix="/api/translation", tags=["translation"])
TranslationServiceDependency = Annotated[
    TranslationService,
    Depends(get_translation_service),
]


@router.get("/status", response_model=TranslationStatusResponse)
def translation_status(
    service: TranslationServiceDependency,
) -> TranslationStatusResponse:
    return TranslationStatusResponse(
        provider=service.provider_name,
        source_language=service.default_source_language,
        target_language=service.default_target_language,
    )


@router.post("", response_model=TranslationApiResponse)
def translate(
    payload: TranslationApiRequest,
    service: TranslationServiceDependency,
) -> TranslationApiResponse:
    try:
        result = service.translate(
            payload.source_text,
            source_language=payload.source_language,
            target_language=payload.target_language,
            request_id=payload.request_id,
        )
    except TextNormalizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except TranslationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="translation provider failed",
        ) from exc

    return TranslationApiResponse(
        source_text=result.source_text,
        translated_text=result.translated_text,
        source_language=result.source_language,
        target_language=result.target_language,
        provider=result.provider,
        request_id=result.request_id,
    )
