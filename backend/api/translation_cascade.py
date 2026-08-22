from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.translation.errors import TextNormalizationError, TranslationError
from backend.models.translation_cascade import (
    TranslationCascadeAttempt,
    TranslationCascadeRequest,
    TranslationCascadeResponse,
)
from backend.services.translation_fallback_service import TranslationFallbackService

router = APIRouter(prefix="/api/translation", tags=["translation"])


def get_translation_fallback_service() -> TranslationFallbackService:
    return TranslationFallbackService()


TranslationFallbackDependency = Annotated[
    TranslationFallbackService,
    Depends(get_translation_fallback_service),
]


@router.post("/cascade", response_model=TranslationCascadeResponse)
def translate_with_fallback(
    payload: TranslationCascadeRequest,
    service: TranslationFallbackDependency,
) -> TranslationCascadeResponse:
    try:
        result = service.translate(
            payload.source_text,
            source_language=payload.source_language,
            target_language=payload.target_language,
            request_id=payload.request_id,
            provider_mode=payload.provider_mode,
        )
    except TextNormalizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except TranslationError as exc:
        detail_by_mode = {
            "youdao_web": "Youdao translation is unavailable.",
            "google_web": "Google translation is unavailable.",
            "ai": "AI translation is unavailable.",
            "auto": "Youdao, Google, and AI translation are unavailable.",
        }
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail_by_mode[payload.provider_mode],
        ) from exc

    return TranslationCascadeResponse(
        source_text=result.source_text,
        translated_text=result.translated_text,
        source_language=result.source_language,
        target_language=result.target_language,
        provider=result.provider,
        model=result.model,
        request_id=result.request_id,
        fallback_level=result.fallback_level,
        notice=result.notice,
        attempts=[
            TranslationCascadeAttempt(provider=item.provider, status=item.status)
            for item in result.attempts
        ],
    )
