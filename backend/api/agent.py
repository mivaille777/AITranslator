from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.ai.errors import AIConfigurationError, AIError
from backend.agent_core.events import AgentEvent
from backend.agent_core.runtime import AgentRuntime
from backend.agent_core.state import AgentState
from backend.api.agent_dependencies import get_agent_runtime
from backend.api.dependencies import get_agent_tool_registry
from backend.models.agent_tools import (
    AgentPlan,
    AgentRunRequest,
    AgentRunResponse,
    AgentRunTraceResponse,
    AgentToolCatalogResponse,
    AgentToolDefinition,
    AgentToolExecuteRequest,
    AgentToolExecuteResponse,
    AgentTraceEvent,
)
from backend.services.agent_tool_registry import AgentToolExecutionResult, AgentToolRegistry

router = APIRouter(prefix="/api/agent", tags=["agent"])
AgentToolRegistryDependency = Annotated[
    AgentToolRegistry,
    Depends(get_agent_tool_registry),
]
AgentRuntimeDependency = Annotated[
    AgentRuntime,
    Depends(get_agent_runtime),
]


def _tool_response(result: AgentToolExecutionResult) -> AgentToolExecuteResponse:
    return AgentToolExecuteResponse(
        tool_name=result.tool_name,
        output_text=result.output_text,
        effect=result.effect,
        provider=result.provider,
        model=result.model,
        request_id=result.request_id,
        data=result.data or {},
    )


def _state_tool_response(result: dict[str, Any]) -> AgentToolExecuteResponse:
    payload = dict(result)
    payload["data"] = dict(payload.get("data") or {})
    return AgentToolExecuteResponse.model_validate(payload)


def _state_from_run_request(payload: AgentRunRequest) -> AgentState:
    context = payload.model_dump(
        exclude={
            "session_id",
            "user_message",
            "source_text",
        }
    )
    return AgentState(
        session_id=payload.session_id,
        user_input=payload.user_message,
        selected_text=payload.source_text,
        browser_context=context,
    )


def _run_response(state: AgentState) -> AgentRunResponse:
    response = state.response
    tool_result = (
        _state_tool_response(state.tool_results[-1]) if state.tool_results else None
    )
    return AgentRunResponse(
        status=str(response.get("status", "completed") or "completed"),
        plan=AgentPlan.model_validate(state.planned_action),
        output_text=str(response.get("output_text", "") or ""),
        provider=str(response.get("provider", "") or ""),
        model=str(response.get("model", "") or ""),
        request_id=max(0, int(response.get("request_id", 0) or 0)),
        tool_result=tool_result,
    )


def _execute_runtime(payload: AgentRunRequest, runtime: AgentRuntime) -> AgentState:
    try:
        return runtime.execute(_state_from_run_request(payload))
    except AIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _trace_event(sequence: int, event: AgentEvent) -> AgentTraceEvent:
    return AgentTraceEvent(
        sequence=sequence,
        event_type=event.event_type.value,
        timestamp=event.timestamp,
        payload=event.payload,
    )


def _trace_response(state: AgentState, runtime: AgentRuntime) -> AgentRunTraceResponse:
    return AgentRunTraceResponse(
        session_id=state.session_id,
        ui_mode=state.ui_mode,
        run=_run_response(state),
        events=[_trace_event(index, event) for index, event in enumerate(runtime.events)],
    )


def _stream_error_code(exc: Exception) -> str:
    if isinstance(exc, AIConfigurationError):
        return "configuration"
    if isinstance(exc, AIError):
        return "provider"
    if isinstance(exc, ValueError):
        return "invalid_request"
    return "internal"


def _consume_background_task(task: asyncio.Task[None]) -> None:
    with suppress(asyncio.CancelledError, Exception):
        task.result()


@router.get("/tools", response_model=AgentToolCatalogResponse)
def list_agent_tools(registry: AgentToolRegistryDependency) -> AgentToolCatalogResponse:
    return AgentToolCatalogResponse(
        tools=[AgentToolDefinition(**asdict(spec)) for spec in registry.list_tools()]
    )


@router.post("/tools/{tool_name}/execute", response_model=AgentToolExecuteResponse)
def execute_agent_tool(
    tool_name: str,
    payload: AgentToolExecuteRequest,
    registry: AgentToolRegistryDependency,
) -> AgentToolExecuteResponse:
    try:
        result = registry.execute(tool_name, **payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except AIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return _tool_response(result)


@router.post("/run", response_model=AgentRunResponse)
def run_product_agent(
    payload: AgentRunRequest,
    runtime: AgentRuntimeDependency,
) -> AgentRunResponse:
    return _run_response(_execute_runtime(payload, runtime))


@router.post("/run/trace", response_model=AgentRunTraceResponse)
def run_product_agent_trace(
    payload: AgentRunRequest,
    runtime: AgentRuntimeDependency,
) -> AgentRunTraceResponse:
    state = _execute_runtime(payload, runtime)
    return _trace_response(state, runtime)


@router.websocket("/stream")
async def stream_product_agent(
    websocket: WebSocket,
    runtime: AgentRuntimeDependency,
) -> None:
    """Stream Agent Core lifecycle events while the synchronous agent executes.

    The transport is observational: planning, confirmation policy and tool side
    effects remain owned by ProductAgentService and AgentToolRegistry.
    """

    await websocket.accept()
    producer_task: asyncio.Task[None] | None = None

    try:
        try:
            incoming = await websocket.receive_json()
        except WebSocketDisconnect:
            return

        if not isinstance(incoming, dict) or incoming.get("type") != "start":
            await websocket.send_json(
                {
                    "type": "error",
                    "request_id": 0,
                    "session_id": "",
                    "code": "invalid_request",
                    "message": "Expected an Agent stream start request.",
                }
            )
            return

        try:
            payload = AgentRunRequest.model_validate(incoming.get("request"))
        except ValidationError as exc:
            await websocket.send_json(
                {
                    "type": "error",
                    "request_id": 0,
                    "session_id": "",
                    "code": "invalid_request",
                    "message": str(exc.errors()[0].get("msg") if exc.errors() else "Invalid Agent request."),
                }
            )
            return

        request_id = payload.request_id
        session_id = payload.session_id
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        await websocket.send_json(
            {
                "type": "accepted",
                "request_id": request_id,
                "session_id": session_id,
            }
        )

        def enqueue(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def observe(event: AgentEvent) -> None:
            sequence = max(0, len(runtime.events) - 1)
            enqueue(
                {
                    "type": "activity",
                    "request_id": request_id,
                    "session_id": session_id,
                    "event": _trace_event(sequence, event).model_dump(mode="json"),
                }
            )

        def produce() -> None:
            try:
                state = runtime.execute(
                    _state_from_run_request(payload),
                    event_sink=observe,
                )
                trace = _trace_response(state, runtime)
                enqueue(
                    {
                        "type": "done",
                        "request_id": request_id,
                        "session_id": session_id,
                        "trace": trace.model_dump(mode="json"),
                    }
                )
            except Exception as exc:
                enqueue(
                    {
                        "type": "error",
                        "request_id": request_id,
                        "session_id": session_id,
                        "code": _stream_error_code(exc),
                        "message": str(exc) or "Agent execution failed.",
                    }
                )

        producer_task = asyncio.create_task(asyncio.to_thread(produce))
        producer_task.add_done_callback(_consume_background_task)

        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event.get("type") in {"done", "error"}:
                return
    except WebSocketDisconnect:
        return
