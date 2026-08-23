from __future__ import annotations

from typing import Any

from backend.agent_tools.base import TypedAgentToolDefinition
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
from backend.agent_tools.writing import (
    PolishSelectionArgs,
    WritingAgentTool,
    WritingResultData,
    build_writing_tool_definition,
)


class BuiltinAgentToolExecutors:
    """Compatibility container for pre-Stage-10.4 tool-builder callers.

    Production registry assembly no longer executes capabilities through this
    class. It only retains service references so the legacy combined builder can
    reproduce the historical seven-tool catalog for older integrations/tests.
    """

    def __init__(
        self,
        *,
        quick_action_service: Any,
        research_note_service: Any | None = None,
    ) -> None:
        self._quick_action_service = quick_action_service
        self._research_note_service = research_note_service


def build_builtin_tool_definitions(
    executors: BuiltinAgentToolExecutors,
    *,
    translation_definition: TypedAgentToolDefinition | None = None,
) -> tuple[TypedAgentToolDefinition, ...]:
    """Compatibility builder over the dedicated capability definitions.

    Without ``translation_definition`` this preserves the old Stage 10.3
    behavior of returning only the remaining writing definition. When an older
    Stage 10.1 caller injects Translation, the historical seven-tool catalog is
    reconstructed entirely from dedicated capability owners.
    """

    writing_definition = build_writing_tool_definition(
        WritingAgentTool(quick_action_service=executors._quick_action_service)
    )
    if translation_definition is None:
        return (writing_definition,)

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
        writing_definition,
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
    "WritingResultData",
    "build_builtin_tool_definitions",
]
