from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.agent_core.context import ReadingContextProvider
from backend.agent_core.product_adapter import ProductAgentRuntimeAdapter
from backend.agent_core.runtime import AgentRuntime
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
    conversation_service: AgentConversationServiceDependency,
    trace_store: AgentTraceStoreDependency = None,
) -> AgentRuntime:
    """Build one lightweight Agent Core runtime for the current API request.

    Runtime execution state remains request-scoped. Product capabilities and
    durable Conversation storage are shared services injected through stable
    adapters; the Agent adapter coordinates one exchange with the existing
    Conversation lifecycle before and after every run.
    """

    return AgentRuntime(
        context_provider=ReadingContextProvider(resolver),
        workflow_adapter=ProductAgentRuntimeAdapter(
            service,
            conversation_service=conversation_service,
        ),
        run_recorder=trace_store.record if trace_store is not None else None,
    )


__all__ = ["get_agent_conversation_service", "get_agent_runtime"]
