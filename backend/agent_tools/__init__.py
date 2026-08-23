"""Strongly typed Agent tool contracts and capability definitions."""

from backend.agent_tools.base import (
    AgentToolExecutionResult,
    AgentToolInvocationContext,
    AgentToolModel,
    AgentToolSpec,
    TypedAgentToolDefinition,
)
from backend.agent_tools.reading import (
    InspectReadingContextResultData,
    QuickActionResultData,
    ReadingAgentTools,
    build_reading_tool_definitions,
)
from backend.agent_tools.translation import (
    TranslateSelectionArgs,
    TranslationAgentTool,
    TranslationResultData,
    build_translation_tool_definition,
)

__all__ = [
    "AgentToolExecutionResult",
    "AgentToolInvocationContext",
    "AgentToolModel",
    "AgentToolSpec",
    "InspectReadingContextResultData",
    "QuickActionResultData",
    "ReadingAgentTools",
    "TranslateSelectionArgs",
    "TranslationAgentTool",
    "TranslationResultData",
    "TypedAgentToolDefinition",
    "build_reading_tool_definitions",
    "build_translation_tool_definition",
]
