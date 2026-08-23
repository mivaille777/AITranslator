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

_AGENT_DETAIL_TEXT_LIMIT = 3_000
_AGENT_OUTPUT_SOURCE_LIMIT = 500
_AGENT_OUTPUT_NOTE_LIMIT = 1_000


class SaveResearchNoteArgs(AgentToolModel):
    user_note: str = Field(default="", max_length=20_000)
    ai_content: str = Field(default="", max_length=30_000)
    conversation_id: str = Field(default="", max_length=128)


class SaveResearchNotePlannerArgs(AgentToolModel):
    user_note: str = Field(default="", max_length=4_000)


class ListResearchNotesArgs(AgentToolModel):
    limit: int = Field(default=5, ge=1, le=20)


class GetResearchNoteArgs(AgentToolModel):
    note_id: str = Field(min_length=1, max_length=128)


class UpdateResearchNoteArgs(AgentToolModel):
    note_id: str = Field(min_length=1, max_length=128)
    user_note: str = Field(default="", max_length=20_000)


class UpdateResearchNotePlannerArgs(AgentToolModel):
    note_id: str = Field(min_length=1, max_length=128)
    user_note: str = Field(default="", max_length=4_000)


class ResearchNoteResultData(AgentToolModel):
    note_id: str
    created: bool
    display_title: str
    excerpt: str
    updated_at: str
    conversation_id: str = ""


class ResearchNoteSummaryData(AgentToolModel):
    note_id: str = Field(max_length=128)
    display_title: str = Field(max_length=1024)
    excerpt: str = Field(max_length=512)
    updated_at: str = Field(max_length=128)
    resource_title: str = Field(default="", max_length=1024)
    section_heading: str = Field(default="", max_length=1024)
    source_kind: str = Field(default="", max_length=128)
    conversation_id: str = Field(default="", max_length=128)


class ResearchNoteDetailData(AgentToolModel):
    note_id: str = Field(max_length=128)
    created_at: str = Field(default="", max_length=128)
    updated_at: str = Field(default="", max_length=128)
    display_title: str = Field(max_length=1024)
    resource_url: str = Field(default="", max_length=4096)
    resource_title: str = Field(default="", max_length=1024)
    section_heading: str = Field(default="", max_length=1024)
    source_kind: str = Field(default="", max_length=128)
    source_text: str = Field(default="", max_length=_AGENT_DETAIL_TEXT_LIMIT)
    translated_text: str = Field(default="", max_length=_AGENT_DETAIL_TEXT_LIMIT)
    ai_content: str = Field(default="", max_length=_AGENT_DETAIL_TEXT_LIMIT)
    ai_action: str = Field(default="", max_length=128)
    user_note: str = Field(default="", max_length=_AGENT_DETAIL_TEXT_LIMIT)
    conversation_id: str = Field(default="", max_length=128)


class ResearchNoteListResultData(AgentToolModel):
    notes: list[ResearchNoteSummaryData] = Field(default_factory=list)
    count: int = Field(default=0, ge=0)


class ResearchNoteLookupResultData(AgentToolModel):
    found: bool
    note: ResearchNoteDetailData | None = None


class ResearchNoteUpdateResultData(AgentToolModel):
    updated: bool
    note: ResearchNoteDetailData | None = None


def _bounded_text(value: Any, limit: int) -> str:
    text = str(value or "").replace("\x00", "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def _summary_data(note: Any) -> dict[str, Any]:
    return {
        "note_id": _bounded_text(note.note_id, 128),
        "display_title": _bounded_text(note.display_title, 1024),
        "excerpt": _bounded_text(note.excerpt, 512),
        "updated_at": _bounded_text(note.updated_at, 128),
        "resource_title": _bounded_text(getattr(note, "resource_title", ""), 1024),
        "section_heading": _bounded_text(getattr(note, "section_heading", ""), 1024),
        "source_kind": _bounded_text(getattr(note, "source_kind", ""), 128),
        "conversation_id": _bounded_text(getattr(note, "conversation_id", ""), 128),
    }


def _detail_data(note: Any) -> dict[str, Any]:
    return {
        "note_id": _bounded_text(note.note_id, 128),
        "created_at": _bounded_text(getattr(note, "created_at", ""), 128),
        "updated_at": _bounded_text(getattr(note, "updated_at", ""), 128),
        "display_title": _bounded_text(note.display_title, 1024),
        "resource_url": _bounded_text(getattr(note, "resource_url", ""), 4096),
        "resource_title": _bounded_text(getattr(note, "resource_title", ""), 1024),
        "section_heading": _bounded_text(getattr(note, "section_heading", ""), 1024),
        "source_kind": _bounded_text(getattr(note, "source_kind", ""), 128),
        "source_text": _bounded_text(getattr(note, "source_text", ""), _AGENT_DETAIL_TEXT_LIMIT),
        "translated_text": _bounded_text(
            getattr(note, "translated_text", ""), _AGENT_DETAIL_TEXT_LIMIT
        ),
        "ai_content": _bounded_text(getattr(note, "ai_content", ""), _AGENT_DETAIL_TEXT_LIMIT),
        "ai_action": _bounded_text(getattr(note, "ai_action", ""), 128),
        "user_note": _bounded_text(getattr(note, "user_note", ""), _AGENT_DETAIL_TEXT_LIMIT),
        "conversation_id": _bounded_text(getattr(note, "conversation_id", ""), 128),
    }


class ResearchAgentTools:
    """Agent-facing boundary for persisted research memory capabilities."""

    def __init__(self, *, research_note_service: Any) -> None:
        self._research_note_service = research_note_service

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

    def list_research_notes(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        typed = cast(ListResearchNotesArgs, args)
        notes = tuple(self._research_note_service.list_recent(limit=typed.limit))
        summaries = [_summary_data(note) for note in notes]
        if summaries:
            lines = [
                f"- {item['note_id']}: {item['display_title']} — {item['excerpt']}"
                for item in summaries
            ]
            output_text = "Recent research notes:\n" + "\n".join(lines)
        else:
            output_text = "No research notes found."
        return AgentToolExecutionResult(
            tool_name="list_research_notes",
            output_text=output_text,
            effect="read",
            request_id=context.request_id,
            data={"notes": summaries, "count": len(summaries)},
        )

    def get_research_note(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        typed = cast(GetResearchNoteArgs, args)
        note = self._research_note_service.get(typed.note_id)
        if note is None:
            return AgentToolExecutionResult(
                tool_name="get_research_note",
                output_text=f"Research note not found: {typed.note_id}",
                effect="read",
                request_id=context.request_id,
                data={"found": False, "note": None},
            )

        detail = _detail_data(note)
        output_text = (
            f"Research note {typed.note_id}: {detail['display_title']}\n"
            f"Source excerpt: {_bounded_text(detail['source_text'], _AGENT_OUTPUT_SOURCE_LIMIT)}\n"
            f"User note: {_bounded_text(detail['user_note'], _AGENT_OUTPUT_NOTE_LIMIT)}"
        )
        return AgentToolExecutionResult(
            tool_name="get_research_note",
            output_text=output_text,
            effect="read",
            request_id=context.request_id,
            data={"found": True, "note": detail},
        )

    def update_research_note(
        self,
        context: AgentToolInvocationContext,
        args: BaseModel,
    ) -> AgentToolExecutionResult:
        typed = cast(UpdateResearchNoteArgs, args)
        note = self._research_note_service.update_user_note(
            typed.note_id,
            typed.user_note,
        )
        if note is None:
            return AgentToolExecutionResult(
                tool_name="update_research_note",
                output_text=f"Research note not found: {typed.note_id}",
                effect="write",
                request_id=context.request_id,
                data={"updated": False, "note": None},
            )

        detail = _detail_data(note)
        return AgentToolExecutionResult(
            tool_name="update_research_note",
            output_text=f"Updated research note: {note.display_title}",
            effect="write",
            request_id=context.request_id,
            data={"updated": True, "note": detail},
        )


def build_research_tool_definitions(
    tools: ResearchAgentTools,
) -> tuple[TypedAgentToolDefinition, ...]:
    return (
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
            executor=tools.save_research_note,
            planner_args_model=SaveResearchNotePlannerArgs,
            retry_policy="never",
        ),
        typed_tool_definition(
            name="list_research_notes",
            title="List research notes",
            description="List recent persisted Research Notes so the Agent can inspect available research memory.",
            category="research",
            effect="read",
            requires_reading_context=False,
            requires_confirmation=False,
            args_model=ListResearchNotesArgs,
            result_model=ResearchNoteListResultData,
            executor=tools.list_research_notes,
            retry_policy="safe",
        ),
        typed_tool_definition(
            name="get_research_note",
            title="Get research note",
            description="Load one bounded persisted Research Note by note identifier.",
            category="research",
            effect="read",
            requires_reading_context=False,
            requires_confirmation=False,
            args_model=GetResearchNoteArgs,
            result_model=ResearchNoteLookupResultData,
            executor=tools.get_research_note,
            retry_policy="safe",
        ),
        typed_tool_definition(
            name="update_research_note",
            title="Update research note",
            description="Replace the user annotation on one persisted Research Note.",
            category="research",
            effect="write",
            requires_reading_context=False,
            requires_confirmation=True,
            args_model=UpdateResearchNoteArgs,
            result_model=ResearchNoteUpdateResultData,
            executor=tools.update_research_note,
            planner_args_model=UpdateResearchNotePlannerArgs,
            retry_policy="never",
        ),
    )


__all__ = [
    "GetResearchNoteArgs",
    "ListResearchNotesArgs",
    "ResearchAgentTools",
    "ResearchNoteDetailData",
    "ResearchNoteListResultData",
    "ResearchNoteLookupResultData",
    "ResearchNoteResultData",
    "ResearchNoteSummaryData",
    "ResearchNoteUpdateResultData",
    "SaveResearchNoteArgs",
    "SaveResearchNotePlannerArgs",
    "UpdateResearchNoteArgs",
    "UpdateResearchNotePlannerArgs",
    "build_research_tool_definitions",
]
