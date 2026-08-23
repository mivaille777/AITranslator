from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, Field

from backend.agent_tools.base import (
    AgentToolExecutionResult,
    AgentToolInvocationContext,
    AgentToolModel,
    TypedAgentToolDefinition,
    typed_tool_definition,
)
from backend.agent_tools.reading import (
    InspectReadingContextResultData,
    QuickActionResultData,
    ReadingAgentTools,
    build_reading_tool_definitions,
)
from backend.agent_tools.research import (
    ResearchAgentTools,
    ResearchNoteResultData,
    SaveResearchNoteArgs,
    SaveResearchNotePlannerArgs,
    build_research_tool_definitions,
)
from backend.agent_tools.translation import (
    TranslateSelectionArgs,
    TranslationResultData,
)


class PolishSelectionArgs(AgentToolModel):
    style: str = Field(default="academic", min_length=1, max_length=64)


class BuiltinAgentToolExecutors:
    """Executor collection for the remaining writing capability.

    Translation, Reading, and Research now own dedicated Agent Tool boundaries.
    Constructor fields for earlier Stage 10 callers remain available so the
    legacy combined builder can still expose the pre-refactor catalog.
    """

    def __init__(
        self,
        *,
        quick_action_service: Any,
        research_note_service: Any | None = None,
    ) -> None:
        self._quick_action_service = quick_action_service
        self._research_note_service = research_note_service

    def polish_selection(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        typed = cast(PolishSelectionArgs, args)
        result = self._quick_action_service.run(
            action="ai_polish",
            **context.reading_payload(),
            style=typed.style,
            request_id=context.request_id,
        )
        return AgentToolExecutionResult(
            tool_name="polish_selection",
            output_text=result.output_text,
            effect="compute",
            provider=result.provider,
            model=result.model,
            request_id=result.request_id,
            data={"action": result.action},
        )


def build_builtin_tool_definitions(
    executors: BuiltinAgentToolExecutors,
    *,
    translation_definition: TypedAgentToolDefinition | None = None,
) -> tuple[TypedAgentToolDefinition, ...]:
    """Build the remaining built-in definitions.

    ``translation_definition`` is retained as a Stage 10.1 compatibility path.
    Production registry assembly composes Translation, Reading, Research, and
    the remaining writing tool independently. Older callers that still inject
    Translation receive the legacy seven-tool catalog without moving capability
    ownership back into this module.
    """

    remaining = (
        typed_tool_definition(
            name="polish_selection",
            title="Polish selection",
            description="Polish the selected text while preserving its language and meaning.",
            category="writing",
            effect="compute",
            requires_reading_context=True,
            requires_confirmation=False,
            args_model=PolishSelectionArgs,
            result_model=QuickActionResultData,
            executor=executors.polish_selection,
            planner_args_model=PolishSelectionArgs,
            retry_policy="safe",
        ),
    )

    if translation_definition is None:
        return remaining

    reading_definitions = build_reading_tool_definitions(
        ReadingAgentTools(quick_action_service=executors._quick_action_service)
    )
    research_definitions = build_research_tool_definitions(
        ResearchAgentTools(research_note_service=executors._research_note_service)
    )
    return (
        reading_definitions[0],
        translation_definition,
        *reading_definitions[1:],
        *remaining,
        research_definitions[0],
    )


__all__ = [
    "BuiltinAgentToolExecutors",
    "InspectReadingContextResultData",
    "PolishSelectionArgs",
    "QuickActionResultData",
    "ResearchNoteResultData",
    "SaveResearchNoteArgs",
    "SaveResearchNotePlannerArgs",
    "TranslateSelectionArgs",
    "TranslationResultData",
    "build_builtin_tool_definitions",
]
