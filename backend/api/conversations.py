from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import get_conversation_store_service
from backend.models.conversations import (
    ConversationDeleteResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationRenameRequest,
    ConversationSummaryResponse,
)
from backend.services.conversation_store_service import (
    ConversationStoreService,
    StoredConversation,
    StoredMessage,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
ConversationStoreDependency = Annotated[
    ConversationStoreService,
    Depends(get_conversation_store_service),
]


def _message_response(message: StoredMessage) -> ConversationMessageResponse:
    return ConversationMessageResponse(
        message_id=message.message_id,
        conversation_id=message.conversation_id,
        request_id=message.request_id,
        role=message.role,
        content=message.content,
        status=message.status,
        provider=message.provider,
        model=message.model,
        error_code=message.error_code,
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


def _summary_response(conversation: StoredConversation) -> ConversationSummaryResponse:
    return ConversationSummaryResponse(
        conversation_id=conversation.conversation_id,
        session_id=conversation.session_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        provider=conversation.provider,
        model=conversation.model,
        resource_title=conversation.resource_title,
        section_heading=conversation.section_heading,
        source_kind=conversation.source_kind,
    )


def _detail_response(conversation: StoredConversation) -> ConversationDetailResponse:
    return ConversationDetailResponse(
        **_summary_response(conversation).model_dump(),
        source_text=conversation.source_text,
        translated_text=conversation.translated_text,
        source_language=conversation.source_language,
        target_language=conversation.target_language,
        resource_url=conversation.resource_url,
        context_before=conversation.context_before,
        context_after=conversation.context_after,
        messages=[_message_response(message) for message in conversation.messages],
    )


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    service: ConversationStoreDependency,
    limit: int = Query(default=30, ge=1, le=50),
) -> ConversationListResponse:
    return ConversationListResponse(
        conversations=[_summary_response(item) for item in service.list_recent(limit=limit)]
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: str,
    service: ConversationStoreDependency,
) -> ConversationDetailResponse:
    conversation = service.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return _detail_response(conversation)


@router.patch("/{conversation_id}", response_model=ConversationDetailResponse)
def rename_conversation(
    conversation_id: str,
    payload: ConversationRenameRequest,
    service: ConversationStoreDependency,
) -> ConversationDetailResponse:
    try:
        conversation = service.rename(conversation_id, payload.title)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return _detail_response(conversation)


@router.delete("/{conversation_id}", response_model=ConversationDeleteResponse)
def delete_conversation(
    conversation_id: str,
    service: ConversationStoreDependency,
) -> ConversationDeleteResponse:
    return ConversationDeleteResponse(
        deleted=service.delete(conversation_id),
        conversation_id=conversation_id,
    )
