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
from backend.agent_tools.translation import (
    TranslateSelectionArgs,
    TranslationResultData,
)


class PolishSelectionArgs(AgentToolModel):
    style: str = Field(default="academic", min_length=1, max_length=64)


class SaveResearchNoteArgs(AgentToolModel):
    user_note: str = Field(default="", max_length=20_000)
    ai_content: str = Field(default="", max_length=30_000)
    conversation_id: str = Field(default="", max_length=128)


class SaveResearchNotePlannerArgs(AgentToolModel):
    user_note: str = Field(default="", max_length=4_000)


class ResearchNoteResultData(AgentToolModel):
    note_id: str
    created: bool
    display_title: str
    excerpt: str
    updated_at: str
    conversation_id: str = ""


class BuiltinAgentToolExecutors:
    """Executors for remaining writing and research capabilities.

    Translation and Reading now own dedicated Agent Tool boundaries. This
    collection remains as the compatibility home for capabilities that will be
    separated in later Stage 10 batches.
    """

    def __init__(
        self,
        *,
        quick_action_service: Any,
        research_note_service: Any,
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

    def save_research_note(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        typed = cast(SaveResearchNoteArgs, args)
        result = self._research_note_service.save(
            **context.reading_payload(),
            ai_content=typed.ai_content,
            ai_action=context.ai_action,
            user_note=typed.user_note,
            conversation_id=typed.conversation_id,
        )
        note = result.note
        return AgentToolExecutionResult(
            tool_name="save_research_note",
            output_text=f"Saved research note: {note.display_title}",
            effect="write",
            request_id=context.request_id,
            data={
                "note_id": note.note_id,
                "created": result.created,
                "display_title": note.display_title,
                "excerpt": note.excerpt,
                "updated_at": note.updated_at,
                "conversation_id": note.conversation_id,
            },
        )


def build_builtin_tool_definitions(
    executors: BuiltinAgentToolExecutors,
    *,
    translation_definition: TypedAgentToolDefinition | None = None,
) -> tuple[TypedAgentToolDefinition, ...]:
    """Build the remaining built-in definitions.

    ``translation_definition`` is retained as a Stage 10.1 compatibility path.
    Production Stage 10.2 registry assembly composes Translation, Reading, and
    remaining built-ins independently. Older callers that still inject a
    translation definition receive the legacy combined catalog without moving
    implementation ownership back into this module.
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
        typed_tool_definition(
            name="save_research_note",
            title="Save research note",
            description="Persist the current reading selection and optional AI evidence into Research Notes.",
            category="research",
            effect="write",
            requires_reading_context=True,
            requires_confirmation=True,
            args_model=SaveResearchNoteArgs,
            result_model=ResearchNoteResultData,
            executor=executors.save_research_note,
            planner_args_model=SaveResearchNotePlannerArgs,
            retry_policy="never",
        ),
    )

    if translation_definition is None:
        return remaining

    reading_definitions = build_reading_tool_definitions(
        ReadingAgentTools(quick_action_service=executors._quick_action_service)
    )
    return (
        reading_definitions[0],
        translation_definition,
        *reading_definitions[1:],
        *remaining,
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
