from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.agent_core.context import ReadingContextProvider
from backend.agent_core.product_adapter import ProductAgentRuntimeAdapter
from backend.agent_core.runtime import AgentRuntime
from backend.api.agent_observability_dependencies import get_agent_trace_store_service
from backend.api.dependencies import (
    get_product_agent_service,
    get_reading_selection_resolver,
)
from backend.services.product_agent_service import ProductAgentService
from backend.services.reading_selection_resolver import ReadingSelectionResolver

ProductAgentServiceDependency = Annotated[
    ProductAgentService,
    Depends(get_product_agent_service),
]
ReadingSelectionResolverDependency = Annotated[
    ReadingSelectionResolver,
    Depends(get_reading_selection_resolver),
]


def get_agent_runtime(
    service: ProductAgentServiceDependency,
    resolver: ReadingSelectionResolverDependency,
) -> AgentRuntime:
    """Build one lightweight Agent Core runtime for the current API request.

    The underlying product services remain shared through the existing backend
    dependency providers. The runtime itself is request-scoped because its
    event list is mutable execution state and must never leak across concurrent
    requests. Observability persistence is shared and privacy-preserving.
    """

    trace_store = get_agent_trace_store_service()
    return AgentRuntime(
        context_provider=ReadingContextProvider(resolver),
        workflow_adapter=ProductAgentRuntimeAdapter(service),
        run_recorder=trace_store.record,
    )


__all__ = ["get_agent_runtime"]