from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.errors import AIConfigurationError, AIError
from backend.api.dependencies import get_agent_tool_registry
from backend.models.agent_tools import (
    AgentToolCatalogResponse,
    AgentToolDefinition,
    AgentToolExecuteRequest,
    AgentToolExecuteResponse,
)
from backend.services.agent_tool_registry import AgentToolRegistry

router = APIRouter(prefix="/api/agent", tags=["agent"])
AgentToolRegistryDependency = Annotated[
    AgentToolRegistry,
    Depends(get_agent_tool_registry),
]


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

    return AgentToolExecuteResponse(
        tool_name=result.tool_name,
        output_text=result.output_text,
        effect=result.effect,
        provider=result.provider,
        model=result.model,
        request_id=result.request_id,
        data=result.data or {},
    )
