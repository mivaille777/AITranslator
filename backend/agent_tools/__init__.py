"""Strongly typed Agent tool contracts and built-in definitions."""

from backend.agent_tools.base import (
    AgentToolExecutionResult,
    AgentToolInvocationContext,
    AgentToolModel,
    AgentToolSpec,
    TypedAgentToolDefinition,
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
    "TranslateSelectionArgs",
    "TranslationAgentTool",
    "TranslationResultData",
    "TypedAgentToolDefinition",
    "build_translation_tool_definition",
]
