from __future__ import annotations

import asyncio
from contextlib import suppress
from threading import Event
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.ai.errors import AIConfigurationError, AIError
from backend.api.dependencies import get_companion_chat_service
from backend.models.companion import (
    CompanionChatStreamCancel,
    CompanionChatStreamStart,
)
from backend.services.companion_chat_service import CompanionChatService

router = APIRouter(tags=["companion-stream"])
CompanionChatServiceDependency = Annotated[
    CompanionChatService,
    Depends(get_companion_chat_service),
]

_TERMINAL_EVENT_TYPES = frozenset({"done", "error", "cancelled"})


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
    }


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
    conversation_id = str(request.get("session_id", ""))[:128]
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
) -> None:
    await websocket.accept()
    cancel_event = Event()
    producer_task: asyncio.Task[None] | None = None
    sender_task: asyncio.Task[str] | None = None
    receiver_task: asyncio.Task[str] | None = None

    try:
        try:
            incoming = await websocket.receive_json()
        except WebSocketDisconnect:
            return

        try:
            start = CompanionChatStreamStart.model_validate(incoming)
        except ValidationError as exc:
            request_id, conversation_id = _incoming_identity(incoming)
            await websocket.send_json(
                {
                    "type": "error",
                    "request_id": request_id,
                    "conversation_id": conversation_id,
                    "message_id": "",
                    "code": "invalid_request",
                    "message": _validation_message(exc),
                }
            )
            return

        payload = start.request
        request_id = payload.request_id
        conversation_id = payload.session_id
        message_id = uuid4().hex
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        await websocket.send_json(
            {
                "type": "accepted",
                "request_id": request_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
            }
        )

        def emit(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def produce() -> None:
            accumulated: list[str] = []
            try:
                for delta in service.stream(**_stream_kwargs(payload)):
                    if cancel_event.is_set():
                        return
                    accumulated.append(delta)
                    emit(
                        {
                            "type": "delta",
                            "request_id": request_id,
                            "conversation_id": conversation_id,
                            "message_id": message_id,
                            "delta": delta,
                            "accumulated_text": "".join(accumulated),
                        }
                    )
                if cancel_event.is_set():
                    return
                emit(
                    {
                        "type": "done",
                        "request_id": request_id,
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "output_text": "".join(accumulated),
                        "provider": service.provider_name,
                        "model": service.model,
                    }
                )
            except Exception as exc:
                if cancel_event.is_set():
                    return
                emit(
                    {
                        "type": "error",
                        "request_id": request_id,
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "code": _error_code(exc),
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
                        "message_id": message_id,
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
        for task in (sender_task, receiver_task):
            if task is not None and not task.done():
                task.cancel()
        # ``asyncio.to_thread`` cannot forcibly stop the provider thread. The
        # cooperative Event makes it stop on the next provider delta, at which
        # point the underlying response stream is closed by the chat core.
