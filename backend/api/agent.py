from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.errors import AIConfigurationError, AIError
from backend.api.dependencies import get_agent_tool_registry, get_product_agent_service
from backend.models.agent_tools import (
    AgentRunRequest,
    AgentRunResponse,
    AgentToolCatalogResponse,
    AgentToolDefinition,
    AgentToolExecuteRequest,
    AgentToolExecuteResponse,
)
from backend.services.agent_tool_registry import AgentToolExecutionResult, AgentToolRegistry
from backend.services.product_agent_service import ProductAgentService

router = APIRouter(prefix="/api/agent", tags=["agent"])
AgentToolRegistryDependency = Annotated[
    AgentToolRegistry,
    Depends(get_agent_tool_registry),
]
ProductAgentServiceDependency = Annotated[
    ProductAgentService,
    Depends(get_product_agent_service),
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
    service: ProductAgentServiceDependency,
) -> AgentRunResponse:
    try:
        result = service.run(**payload.model_dump())
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

    return AgentRunResponse(
        status=result.status,
        plan=result.plan,
        output_text=result.output_text,
        provider=result.provider,
        model=result.model,
        request_id=result.request_id,
        tool_result=_tool_response(result.tool_result) if result.tool_result else None,
    )
