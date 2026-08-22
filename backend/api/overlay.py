from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import get_overlay_state_service
from backend.models.overlay import (
    OverlayAssistantRequest,
    OverlayCompanionBindingRequest,
    OverlayErrorRequest,
    OverlayLoadingRequest,
    OverlayModeRequest,
    OverlayPresentRequest,
    OverlayStateResponse,
)
from backend.services.overlay_state_service import OverlayState, OverlayStateService

router = APIRouter(prefix="/api/overlay", tags=["overlay"])
OverlayStateServiceDependency = Annotated[
    OverlayStateService,
    Depends(get_overlay_state_service),
]


def _response(state: OverlayState) -> OverlayStateResponse:
    return OverlayStateResponse(
        revision=state.revision,
        visible=state.visible,
        mode=state.mode,
        phase=state.phase,
        context_id=state.context_id,
        source_text=state.source_text,
        translated_text=state.translated_text,
        source_language=state.source_language,
        target_language=state.target_language,
        provider=state.provider,
        message=state.message,
        translation_notice=state.translation_notice,
        resource_url=state.resource_url,
        resource_title=state.resource_title,
        section_heading=state.section_heading,
        context_before=state.context_before,
        context_after=state.context_after,
        source_kind=state.source_kind,
        companion_conversation_id=state.companion_conversation_id,
    )


def _reading_kwargs(payload: OverlayAssistantRequest | OverlayLoadingRequest | OverlayPresentRequest | OverlayErrorRequest) -> dict[str, str]:
    return {
        "resource_url": payload.resource_url,
        "resource_title": payload.resource_title,
        "section_heading": payload.section_heading,
        "context_before": payload.context_before,
        "context_after": payload.context_after,
        "source_kind": payload.source_kind,
    }


@router.get("", response_model=OverlayStateResponse)
def overlay_state(service: OverlayStateServiceDependency) -> OverlayStateResponse:
    return _response(service.snapshot())


@router.post("/mode", response_model=OverlayStateResponse)
def overlay_mode(
    payload: OverlayModeRequest,
    service: OverlayStateServiceDependency,
) -> OverlayStateResponse:
    try:
        state = service.switch_mode(context_id=payload.context_id, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return _response(state)


@router.post("/assistant", response_model=OverlayStateResponse)
def overlay_assistant(
    payload: OverlayAssistantRequest,
    service: OverlayStateServiceDependency,
) -> OverlayStateResponse:
    return _response(
        service.show_assistant(
            context_id=payload.context_id,
            source_text=payload.source_text,
            source_language=payload.source_language,
            target_language=payload.target_language,
            **_reading_kwargs(payload),
        )
    )


@router.post("/loading", response_model=OverlayStateResponse)
def overlay_loading(
    payload: OverlayLoadingRequest,
    service: OverlayStateServiceDependency,
) -> OverlayStateResponse:
    return _response(
        service.show_loading(
            context_id=payload.context_id,
            source_text=payload.source_text,
            source_language=payload.source_language,
            target_language=payload.target_language,
            **_reading_kwargs(payload),
        )
    )


@router.post("/present", response_model=OverlayStateResponse)
def overlay_present(
    payload: OverlayPresentRequest,
    service: OverlayStateServiceDependency,
) -> OverlayStateResponse:
    return _response(
        service.show_translation(
            context_id=payload.context_id,
            source_text=payload.source_text,
            translated_text=payload.translated_text,
            source_language=payload.source_language,
            target_language=payload.target_language,
            provider=payload.provider,
            translation_notice=payload.translation_notice,
            **_reading_kwargs(payload),
        )
    )


@router.post("/translation-failure", response_model=OverlayStateResponse)
def overlay_translation_failure(
    payload: OverlayErrorRequest,
    service: OverlayStateServiceDependency,
) -> OverlayStateResponse:
    return _response(
        service.show_translation_failure(
            context_id=payload.context_id,
            source_text=payload.source_text,
            source_language=payload.source_language,
            target_language=payload.target_language,
            message=payload.message,
            **_reading_kwargs(payload),
        )
    )


@router.post("/error", response_model=OverlayStateResponse)
def overlay_error(
    payload: OverlayErrorRequest,
    service: OverlayStateServiceDependency,
) -> OverlayStateResponse:
    return _response(
        service.show_error(
            context_id=payload.context_id,
            source_text=payload.source_text,
            source_language=payload.source_language,
            target_language=payload.target_language,
            message=payload.message,
            **_reading_kwargs(payload),
        )
    )


@router.post("/companion", response_model=OverlayStateResponse)
def overlay_bind_companion(
    payload: OverlayCompanionBindingRequest,
    service: OverlayStateServiceDependency,
) -> OverlayStateResponse:
    try:
        state = service.bind_companion_conversation(
            context_id=payload.context_id,
            conversation_id=payload.conversation_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return _response(state)


@router.post("/dismiss", response_model=OverlayStateResponse)
def overlay_dismiss(service: OverlayStateServiceDependency) -> OverlayStateResponse:
    return _response(service.dismiss())
