"""LLM gateway dependency and routed service factories."""

from __future__ import annotations

from threading import Lock

from app.ai.chat.service import AIChatService
from app.ai.gateway import LLMGateway
from backend.services.agent_multi_step_planner_service import (
    AgentMultiStepPlannerService,
)
from backend.services.agent_router_service import AgentSemanticRouterService
from backend.services.agent_tool_registry import AgentToolRegistry
from backend.services.companion_chat_service import CompanionChatService
from backend.services.grounded_synthesis_service import GroundedSynthesisService
from backend.services.product_agent_service import ProductAgentService
from backend.services.quick_action_service import QuickActionService
from backend.services.reading_selection_resolver import ReadingSelectionResolver

_gateway: LLMGateway | None = None
_gateway_lock = Lock()


def get_llm_gateway() -> LLMGateway:
    global _gateway
    if _gateway is not None:
        return _gateway
    with _gateway_lock:
        if _gateway is None:
            _gateway = LLMGateway()
        return _gateway


def build_routed_quick_action_service() -> QuickActionService:
    gateway = get_llm_gateway()
    polish_service = gateway.create_text_service("polish")
    reading_service = gateway.create_text_service("reading")
    return QuickActionService(
        text_service=polish_service,
        chat_service=AIChatService(reading_service),
    )


def build_routed_product_agent_service(
    *,
    registry: AgentToolRegistry,
    resolver: ReadingSelectionResolver,
) -> ProductAgentService:
    gateway = get_llm_gateway()
    semantic_router = AgentSemanticRouterService(
        text_service=gateway.create_text_service("planner")
    )
    multi_step_planner = AgentMultiStepPlannerService(
        text_service=gateway.create_text_service("planner")
    )
    synthesis = CompanionChatService(
        text_service=gateway.create_text_service("agent_synthesis"),
        reading_resolver=resolver,
    )
    return ProductAgentService(
        registry=registry,
        chat_service=synthesis,
        grounded_synthesis_service=GroundedSynthesisService(chat_service=synthesis),
        semantic_router=semantic_router,
        multi_step_planner=multi_step_planner,
    )


__all__ = [
    "build_routed_product_agent_service",
    "build_routed_quick_action_service",
    "get_llm_gateway",
]
