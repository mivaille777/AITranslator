from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, Field

from backend.agent_tools.base import (
    AgentToolExecutionResult,
    AgentToolInvocationContext,
    AgentToolModel,
    EmptyToolArgs,
    typed_tool_definition,
)


class TranslateSelectionArgs(AgentToolModel):
    target_language: str = Field(default="zh-CN", min_length=1, max_length=64)


class PolishSelectionArgs(AgentToolModel):
    style: str = Field(default="academic", min_length=1, max_length=64)


class SaveResearchNoteArgs(AgentToolModel):
    user_note: str = Field(default="", max_length=20_000)
    ai_content: str = Field(default="", max_length=30_000)
    conversation_id: str = Field(default="", max_length=128)


class SaveResearchNotePlannerArgs(AgentToolModel):
    user_note: str = Field(default="", max_length=4_000)


class InspectReadingContextResultData(AgentToolModel):
    source_text: str = ""
    translated_text: str = ""
    source_language: str = "auto"
    target_language: str = "zh-CN"
    resource_url: str = ""
    resource_title: str = ""
    section_heading: str = ""
    context_before: str = ""
    context_after: str = ""
    source_kind: str = "desktop"


class TranslationAttemptData(AgentToolModel):
    provider: str
    status: str


class TranslationResultData(AgentToolModel):
    source_language: str = "auto"
    target_language: str = "zh-CN"
    fallback_level: int = Field(default=0, ge=0)
    notice: str = ""
    attempts: list[TranslationAttemptData] = Field(default_factory=list)


class QuickActionResultData(AgentToolModel):
    action: str


class ResearchNoteResultData(AgentToolModel):
    note_id: str
    created: bool
    display_title: str
    excerpt: str
    updated_at: str
    conversation_id: str = ""


class BuiltinAgentToolExecutors:
    def __init__(
        self,
        *,
        translation_service: Any | None,
        translation_fallback_service: Any | None,
        quick_action_service: Any,
        research_note_service: Any,
    ) -> None:
        self._translation_service = translation_service
        self._translation_fallback_service = translation_fallback_service
        self._quick_action_service = quick_action_service
        self._research_note_service = research_note_service

    def inspect_reading_context(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        cast(EmptyToolArgs, args)
        return AgentToolExecutionResult(
            tool_name="inspect_reading_context",
            output_text=context.source_text,
            effect="read",
            request_id=context.request_id,
            data=context.reading_payload(),
        )

    def translate_selection(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        typed = cast(TranslateSelectionArgs, args)
        target_language = typed.target_language or context.target_language

        if self._translation_fallback_service is not None:
            result = self._translation_fallback_service.translate(
                context.source_text,
                source_language=context.source_language,
                target_language=target_language,
                request_id=context.request_id,
            )
            return AgentToolExecutionResult(
                tool_name="translate_selection",
                output_text=result.translated_text,
                effect="compute",
                provider=result.provider,
                model=result.model,
                request_id=result.request_id,
                data={
                    "source_language": result.source_language,
                    "target_language": result.target_language,
                    "fallback_level": result.fallback_level,
                    "notice": result.notice,
                    "attempts": [
                        {"provider": item.provider, "status": item.status}
                        for item in result.attempts
                    ],
                },
            )

        if self._translation_service is None:
            raise RuntimeError("Agent translation service is unavailable.")

        result = self._translation_service.translate(
            context.source_text,
            source_language=context.source_language,
            target_language=target_language,
            request_id=context.request_id,
        )
        return AgentToolExecutionResult(
            tool_name="translate_selection",
            output_text=result.translated_text,
            effect="compute",
            provider=result.provider,
            request_id=result.request_id,
            data={
                "source_language": result.source_language,
                "target_language": result.target_language,
                "fallback_level": 0,
                "notice": "",
                "attempts": [],
            },
        )

    def _run_quick_action(
        self,
        *,
        tool_name: str,
        action: str,
        context: AgentToolInvocationContext,
        style: str,
    ) -> AgentToolExecutionResult:
        result = self._quick_action_service.run(
            action=action,
            **context.reading_payload(),
            style=style,
            request_id=context.request_id,
        )
        return AgentToolExecutionResult(
            tool_name=tool_name,
            output_text=result.output_text,
            effect="compute",
            provider=result.provider,
            model=result.model,
            request_id=result.request_id,
            data={"action": result.action},
        )

    def explain_selection(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        cast(EmptyToolArgs, args)
        return self._run_quick_action(
            tool_name="explain_selection",
            action="reading_explain",
            context=context,
            style=context.style,
        )

    def summarize_selection(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        cast(EmptyToolArgs, args)
        return self._run_quick_action(
            tool_name="summarize_selection",
            action="reading_summarize",
            context=context,
            style=context.style,
        )

    def analyze_section_role(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        cast(EmptyToolArgs, args)
        return self._run_quick_action(
            tool_name="analyze_section_role",
            action="reading_section_role",
            context=context,
            style=context.style,
        )

    def polish_selection(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        typed = cast(PolishSelectionArgs, args)
        return self._run_quick_action(
            tool_name="polish_selection",
            action="ai_polish",
            context=context,
            style=typed.style,
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


def build_builtin_tool_definitions(executors: BuiltinAgentToolExecutors):
    return (
        typed_tool_definition(
            name="inspect_reading_context",
            title="Inspect reading context",
            description="Return the frozen reading selection and nearby source metadata available to the agent.",
            category="context",
            effect="read",
            requires_reading_context=True,
            requires_confirmation=False,
            args_model=EmptyToolArgs,
            result_model=InspectReadingContextResultData,
            executor=executors.inspect_reading_context,
            retry_policy="safe",
        ),
        typed_tool_definition(
            name="translate_selection",
            title="Translate selection",
            description="Translate the current selected text using the deterministic Youdao, Google, then AI fallback chain.",
            category="translation",
            effect="compute",
            requires_reading_context=True,
            requires_confirmation=False,
            args_model=TranslateSelectionArgs,
            result_model=TranslationResultData,
            executor=executors.translate_selection,
            planner_args_model=TranslateSelectionArgs,
            retry_policy="safe",
        ),
        typed_tool_definition(
            name="explain_selection",
            title="Explain selection",
            description="Explain the selected text using the frozen reading context.",
            category="reading",
            effect="compute",
            requires_reading_context=True,
            requires_confirmation=False,
            args_model=EmptyToolArgs,
            result_model=QuickActionResultData,
            executor=executors.explain_selection,
            retry_policy="safe",
        ),
        typed_tool_definition(
            name="summarize_selection",
            title="Summarize selection",
            description="Summarize the selected text using the frozen reading context.",
            category="reading",
            effect="compute",
            requires_reading_context=True,
            requires_confirmation=False,
            args_model=EmptyToolArgs,
            result_model=QuickActionResultData,
            executor=executors.summarize_selection,
            retry_policy="safe",
        ),
        typed_tool_definition(
            name="analyze_section_role",
            title="Analyze section role",
            description="Analyze how the selection functions inside the current section or document context.",
            category="reading",
            effect="compute",
            requires_reading_context=True,
            requires_confirmation=False,
            args_model=EmptyToolArgs,
            result_model=QuickActionResultData,
            executor=executors.analyze_section_role,
            retry_policy="safe",
        ),
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
