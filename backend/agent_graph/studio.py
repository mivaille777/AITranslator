from __future__ import annotations

from typing import Any

from backend.agent_core.product_adapter import ProductAgentRuntimeAdapter
from backend.agent_graph.reading_agent_graph import ReadingAgentGraph
from backend.api.dependencies import (
    get_companion_ownership_service,
    get_conversation_store_service,
    get_product_agent_service,
)
from backend.services.agent_conversation_service import AgentConversationService


def make_graph(config: dict[str, Any] | None = None):
    """Build the production ReadingAgentGraph for LangSmith Studio.

    The CLI calls this factory when ``langgraph dev`` starts. Building lazily
    keeps Studio dependencies and service initialization out of normal FastAPI
    imports and preserves the application's existing production startup path.
    """

    del config
    conversation_service = AgentConversationService(
        store=get_conversation_store_service(),
        ownership=get_companion_ownership_service(),
    )
    adapter = ProductAgentRuntimeAdapter(
        get_product_agent_service(),
        conversation_service=conversation_service,
    )
    return ReadingAgentGraph(adapter).compiled_graph


__all__ = ["make_graph"]
