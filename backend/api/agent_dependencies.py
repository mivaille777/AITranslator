from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.agent_core.context import ReadingContextProvider
from backend.agent_core.product_adapter import ProductAgentRuntimeAdapter
from backend.agent_core.runtime import AgentRuntime
from backend.agent_graph.reading_agent_graph import ReadingAgentGraph
from backend.api.agent_observability_dependencies import get_agent_trace_store_service
from backend.api.dependencies import (
    get_companion_ownership_service,
    get_conversation_store_service,
    get_product_agent_service,
    get_reading_selection_resolver,
)
from backend.services.agent_conversation_service import AgentConversationService
from backend.services.agent_trace_store_service import AgentTraceStoreService
from backend.services.companion_ownership_service import (
    CompanionConversationOwnershipService,
)
from backend.services.conversation_store_service import ConversationStoreService
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
AgentTraceStoreDependency = Annotated[
    AgentTraceStoreService | None,
    Depends(get_agent_trace_store_service),
]
ConversationStoreDependency = Annotated[
    ConversationStoreService,
    Depends(get_conversation_store_service),
]
ConversationOwnershipDependency = Annotated[
    CompanionConversationOwnershipService,
    Depends(get_companion_ownership_service),
]


def get_agent_conversation_service(
    store: ConversationStoreDependency,
    ownership: ConversationOwnershipDependency,
) -> AgentConversationService:
    return AgentConversationService(store=store, ownership=ownership)


AgentConversationServiceDependency = Annotated[
    AgentConversationService,
    Depends(get_agent_conversation_service),
]


def get_agent_runtime(
    service: ProductAgentServiceDependency,
    resolver: ReadingSelectionResolverDependency,
    conversation_service: AgentConversationServiceDependency = None,
    trace_store: AgentTraceStoreDependency = None,
) -> AgentRuntime:
    """Build one request-scoped Agent Runtime backed by ReadingAgentGraph.

    ``AgentRuntime`` remains the outer reliability/telemetry boundary. LangGraph
    owns production workflow orchestration, while the compatibility adapter
    projects existing ProductAgentService results onto ``AgentState`` and keeps
    the shared Conversation lifecycle reusable during the staged migration.

    ``conversation_service`` remains optional for direct unit-test construction.
    FastAPI still resolves it from the dependency metadata carried by
    ``AgentConversationServiceDependency``.
    """

    adapter = ProductAgentRuntimeAdapter(
        service,
        conversation_service=conversation_service,
    )
    graph = ReadingAgentGraph(adapter)
    return AgentRuntime(
        context_provider=ReadingContextProvider(resolver),
        workflow_adapter=graph,
        run_recorder=trace_store.record if trace_store is not None else None,
    )


__all__ = ["get_agent_conversation_service", "get_agent_runtime"]
