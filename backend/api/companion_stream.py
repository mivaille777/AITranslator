from __future__ import annotations

import asyncio
from contextlib import suppress
from threading import Event, Lock
from time import monotonic
from typing import Annotated, Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.ai.errors import AIConfigurationError, AIError
from backend.api.dependencies import (
    get_companion_chat_service,
    get_conversation_store_service,
)
from backend.models.companion import (
    CompanionChatStreamCancel,
    CompanionChatStreamStart,
)
from backend.services.companion_chat_service import CompanionChatService
from backend.services.conversation_store_service import ConversationStoreService

router = APIRouter(tags=["companion-stream"])
CompanionChatServiceDependency = Annotated[
    CompanionChatService,
    Depends(get_companion_chat_service),
]
ConversationStoreDependency = Annotated[
    ConversationStoreService,
    Depends(get_conversation_store_service),
]

_TERMINAL_EVENT_TYPES = frozenset({"done", "error", "cancelled"})
_STREAM_FLUSH_INTERVAL_SECONDS = 0.25
_STREAM_FLUSH_CHARACTER_STEP = 256


def _stream_kwargs(payload: Any) -> dict[str, Any]:
    return {
        "session_id": payload.session_id,
        "user_message": payload.user_message,
        "source_text": payload.source_text,
        "translated_text": payload.translated_text,
        "source_language": payload.source_language,
        "target_language": payload.target_language,
        "resource_url": payload.resource_url,
        "resource_title": payload.resource_title,
        "section_heading": payload.section_heading,
        "context_before": payload.context_before,
        "context_after": payload.context_after,
        "source_kind": payload.source_kind,
        "history": tuple((item.role, item.content) for item in payload.history),
        "request_id": payload.request_id,
        "context_mode": payload.context_mode,
    }


def _begin_exchange(store: ConversationStoreService, payload: Any, request_id: int):
    kwargs = {
        "conversation_id": payload.conversation_id,
        "session_id": payload.session_id,
        "user_message": payload.user_message,
        "request_id": request_id,
        "source_text": payload.source_text,
        "translated_text": payload.translated_text,
        "source_language": payload.source_language,
        "target_language": payload.target_language,
        "resource_url": payload.resource_url,
        "resource_title": payload.resource_title,
        "section_heading": payload.section_heading,
        "context_before": payload.context_before,
        "context_after": payload.context_after,
        "source_kind": payload.source_kind,
    }
    context_aware = getattr(store, "begin_exchange_with_context_mode", None)
    if callable(context_aware):
        return context_aware(context_mode=payload.context_mode, **kwargs)
    return store.begin_exchange(**kwargs)


def _validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid streaming chat request."
    return str(errors[0].get("msg") or "Invalid streaming chat request.")


def _incoming_identity(incoming: object) -> tuple[int, str]:
    if not isinstance(incoming, dict):
        return 0, ""
    request = incoming.get("request")
    if not isinstance(request, dict):
        return 0, ""
    request_id = request.get("request_id", 0)
    if isinstance(request_id, bool) or not isinstance(request_id, int) or request_id < 0:
        request_id = 0
    conversation_id = str(request.get("conversation_id", ""))[:128]
    return request_id, conversation_id


def _error_code(exc: Exception) -> str:
    if isinstance(exc, AIConfigurationError):
        return "configuration"
    if isinstance(exc, AIError):
        return "provider"
    return "internal"


def _consume_background_task(task: asyncio.Task[None]) -> None:
    with suppress(asyncio.CancelledError, Exception):
        task.result()


@router.websocket("/ws/companion/chat")
async def stream_companion_chat(
    websocket: WebSocket,
    service: CompanionChatServiceDependency,
    store: ConversationStoreDependency,
) -> None:
    await websocket.accept()
    cancel_event = Event()
    producer_task: asyncio.Task[None] | None = None
    sender_task: asyncio.Task[str] | None = None
    receiver_task: asyncio.Task[str] | None = None
    assistant_message_id = ""
    conversation_id = ""
    request_id = 0
    terminal_lock = Lock()
    terminal_committed = False
    latest_text_lock = Lock()
    latest_text = ""

    def current_text() -> str:
        with latest_text_lock:
            return latest_text

    def update_latest(value: str) -> None:
        nonlocal latest_text
        with latest_text_lock:
            latest_text = value

    def commit_terminal(
        terminal_status: str,
        *,
        content: str | None = None,
        provider: str = "",
        model: str = "",
        error_code: str = "",
    ) -> bool:
        nonlocal terminal_committed
        with terminal_lock:
            if terminal_committed or not assistant_message_id:
                return False
            store.finalize_message(
                assistant_message_id,
                status=terminal_status,
                content=current_text() if content is None else content,
                provider=provider,
                model=model,
                error_code=error_code,
            )
            terminal_committed = True
            return True

    try:
        try:
            incoming = await websocket.receive_json()
        except WebSocketDisconnect:
            return

        try:
            start = CompanionChatStreamStart.model_validate(incoming)
        except ValidationError as exc:
            invalid_request_id, invalid_conversation_id = _incoming_identity(incoming)
            await websocket.send_json(
                {
                    "type": "error",
                    "request_id": invalid_request_id,
                    "conversation_id": invalid_conversation_id,
                    "message_id": "",
                    "code": "invalid_request",
                    "message": _validation_message(exc),
                }
            )
            return

        payload = start.request
        request_id = payload.request_id
        try:
            exchange = _begin_exchange(store, payload, request_id)
        except (OSError, ValueError) as exc:
            await websocket.send_json(
                {
                    "type": "error",
                    "request_id": request_id,
                    "conversation_id": payload.conversation_id,
                    "message_id": "",
                    "code": "conversation_store",
                    "message": str(exc) or "Unable to persist AI Chat request.",
                }
            )
            return

        conversation_id = exchange.conversation_id
        assistant_message_id = exchange.assistant_message_id
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        await websocket.send_json(
            {
                "type": "accepted",
                "request_id": request_id,
                "conversation_id": conversation_id,
                "message_id": assistant_message_id,
                "user_message_id": exchange.user_message_id,
            }
        )

        def emit(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def produce() -> None:
            accumulated: list[str] = []
            persisted_length = 0
            last_flush = monotonic()
            try:
                for delta in service.stream(**_stream_kwargs(payload)):
                    if cancel_event.is_set():
                        return
                    accumulated.append(delta)
                    text = "".join(accumulated)
                    update_latest(text)
                    now = monotonic()
                    if (
                        len(text) - persisted_length >= _STREAM_FLUSH_CHARACTER_STEP
                        or now - last_flush >= _STREAM_FLUSH_INTERVAL_SECONDS
                    ):
                        store.update_stream(assistant_message_id, text)
                        persisted_length = len(text)
                        last_flush = now
                    emit(
                        {
                            "type": "delta",
                            "request_id": request_id,
                            "conversation_id": conversation_id,
                            "message_id": assistant_message_id,
                            "delta": delta,
                            "accumulated_text": text,
                        }
                    )

                if cancel_event.is_set():
                    return
                text = "".join(accumulated)
                update_latest(text)
                commit_terminal(
                    "complete",
                    content=text,
                    provider=service.provider_name,
                    model=service.model,
                )
                emit(
                    {
                        "type": "done",
                        "request_id": request_id,
                        "conversation_id": conversation_id,
                        "message_id": assistant_message_id,
                        "output_text": text,
                        "provider": service.provider_name,
                        "model": service.model,
                    }
                )
            except Exception as exc:
                if cancel_event.is_set():
                    return
                code = _error_code(exc)
                commit_terminal(
                    "error",
                    provider=service.provider_name,
                    model=service.model,
                    error_code=code,
                )
                emit(
                    {
                        "type": "error",
                        "request_id": request_id,
                        "conversation_id": conversation_id,
                        "message_id": assistant_message_id,
                        "code": code,
                        "message": str(exc) or "AI chat streaming failed.",
                    }
                )

        async def send_events() -> str:
            while True:
                event = await queue.get()
                await websocket.send_json(event)
                if event.get("type") in _TERMINAL_EVENT_TYPES:
                    return str(event.get("type"))

        async def receive_control() -> str:
            while True:
                try:
                    control = await websocket.receive_json()
                except WebSocketDisconnect:
                    cancel_event.set()
                    return "disconnect"

                if not isinstance(control, dict) or control.get("type") != "cancel":
                    continue
                try:
                    cancel = CompanionChatStreamCancel.model_validate(control)
                except ValidationError:
                    continue
                if cancel.request_id != request_id:
                    continue

                cancel_event.set()
                commit_terminal("cancelled", error_code="user_cancelled")
                while True:
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                await queue.put(
                    {
                        "type": "cancelled",
                        "request_id": request_id,
                        "conversation_id": conversation_id,
                        "message_id": assistant_message_id,
                    }
                )
                return "cancel"

        producer_task = asyncio.create_task(asyncio.to_thread(produce))
        producer_task.add_done_callback(_consume_background_task)
        sender_task = asyncio.create_task(send_events())
        receiver_task = asyncio.create_task(receive_control())

        done, _pending = await asyncio.wait(
            {sender_task, receiver_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if receiver_task in done:
            control_result = receiver_task.result()
            if control_result == "cancel":
                with suppress(asyncio.TimeoutError, WebSocketDisconnect):
                    await asyncio.wait_for(sender_task, timeout=1.0)
            else:
                sender_task.cancel()
        else:
            receiver_task.cancel()
    finally:
        cancel_event.set()
        commit_terminal("cancelled", error_code="transport_closed")
        for task in (sender_task, receiver_task):
            if task is not None and not task.done():
                task.cancel()
