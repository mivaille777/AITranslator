from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.errors import AIConfigurationError, AIError
from backend.agent_core.runtime import AgentRuntime
from backend.agent_core.state import AgentState
from backend.api.agent_dependencies import get_agent_runtime
from backend.api.dependencies import get_agent_tool_registry
from backend.models.agent_tools import (
    AgentPlan,
    AgentRunRequest,
    AgentRunResponse,
    AgentToolCatalogResponse,
    AgentToolDefinition,
    AgentToolExecuteRequest,
    AgentToolExecuteResponse,
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
    try:
        state = runtime.execute(_state_from_run_request(payload))
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

    return _run_response(state)
