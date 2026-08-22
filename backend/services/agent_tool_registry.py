from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.services.quick_action_service import QuickActionService
from backend.services.research_note_service import ResearchNoteService
from backend.services.translation_fallback_service import TranslationFallbackService
from backend.services.translation_service import TranslationService


@dataclass(frozen=True, slots=True)
class AgentToolSpec:
    name: str
    title: str
    description: str
    category: str
    effect: str
    requires_reading_context: bool
    requires_confirmation: bool
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AgentToolExecutionResult:
    tool_name: str
    output_text: str
    effect: str
    provider: str = ""
    model: str = ""
    request_id: int = 0
    data: dict[str, Any] | None = None


_TOOL_SPECS = (
    AgentToolSpec(
        name="inspect_reading_context",
        title="Inspect reading context",
        description="Return the frozen reading selection and nearby source metadata available to the agent.",
        category="context",
        effect="read",
        requires_reading_context=True,
        requires_confirmation=False,
        input_schema={},
    ),
    AgentToolSpec(
        name="translate_selection",
        title="Translate selection",
        description="Translate the current selected text using the deterministic Youdao, Google, then AI fallback chain.",
        category="translation",
        effect="compute",
        requires_reading_context=True,
        requires_confirmation=False,
        input_schema={"target_language": {"type": "string"}},
    ),
    AgentToolSpec(
        name="explain_selection",
        title="Explain selection",
        description="Explain the selected text using the frozen reading context.",
        category="reading",
        effect="compute",
        requires_reading_context=True,
        requires_confirmation=False,
        input_schema={},
    ),
    AgentToolSpec(
        name="summarize_selection",
        title="Summarize selection",
        description="Summarize the selected text using the frozen reading context.",
        category="reading",
        effect="compute",
        requires_reading_context=True,
        requires_confirmation=False,
        input_schema={},
    ),
    AgentToolSpec(
        name="analyze_section_role",
        title="Analyze section role",
        description="Analyze how the selection functions inside the current section or document context.",
        category="reading",
        effect="compute",
        requires_reading_context=True,
        requires_confirmation=False,
        input_schema={},
    ),
    AgentToolSpec(
        name="polish_selection",
        title="Polish selection",
        description="Polish the selected text while preserving its language and meaning.",
        category="writing",
        effect="compute",
        requires_reading_context=True,
        requires_confirmation=False,
        input_schema={"style": {"type": "string", "default": "academic"}},
    ),
    AgentToolSpec(
        name="save_research_note",
        title="Save research note",
        description="Persist the current reading selection and optional AI evidence into Research Notes.",
        category="research",
        effect="write",
        requires_reading_context=True,
        requires_confirmation=True,
        input_schema={
            "user_note": {"type": "string"},
            "ai_content": {"type": "string"},
            "conversation_id": {"type": "string"},
        },
    ),
)
_TOOL_BY_NAME = {spec.name: spec for spec in _TOOL_SPECS}


class AgentToolRegistry:
    """Deterministic registry over existing AITranslator capabilities.

    The registry owns tool metadata, validation boundaries and dispatch only.
    Translation, reading AI actions and research persistence remain implemented
    by their existing services so Agent mode cannot silently diverge from the
    normal product behavior.
    """

    def __init__(
        self,
        *,
        translation_service: TranslationService | Any | None = None,
        translation_fallback_service: TranslationFallbackService | Any | None = None,
        quick_action_service: QuickActionService | Any | None = None,
        research_note_service: ResearchNoteService | Any | None = None,
    ) -> None:
        # Explicit translation_service injection remains supported for existing
        # deterministic tests/integrations. Production defaults to the same
        # Youdao -> Google -> AI cascade used by the unified overlay.
        self._translation_service = translation_service
        self._translation_fallback_service = (
            translation_fallback_service
            if translation_fallback_service is not None
            else None if translation_service is not None else TranslationFallbackService()
        )
        self._quick_action_service = quick_action_service or QuickActionService()
        self._research_note_service = research_note_service or ResearchNoteService()

    def list_tools(self) -> tuple[AgentToolSpec, ...]:
        return _TOOL_SPECS

    def get_tool(self, name: str) -> AgentToolSpec | None:
        return _TOOL_BY_NAME.get(str(name or "").strip())

    @staticmethod
    def _context_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_text": str(payload.get("source_text", "") or ""),
            "translated_text": str(payload.get("translated_text", "") or ""),
            "source_language": str(payload.get("source_language", "auto") or "auto"),
            "target_language": str(payload.get("target_language", "zh-CN") or "zh-CN"),
            "resource_url": str(payload.get("resource_url", "") or ""),
            "resource_title": str(payload.get("resource_title", "") or ""),
            "section_heading": str(payload.get("section_heading", "") or ""),
            "context_before": str(payload.get("context_before", "") or ""),
            "context_after": str(payload.get("context_after", "") or ""),
            "source_kind": str(payload.get("source_kind", "desktop") or "desktop"),
        }

    def execute(self, name: str, **payload: Any) -> AgentToolExecutionResult:
        spec = self.get_tool(name)
        if spec is None:
            raise KeyError(f"Unknown agent tool: {name}")

        context = self._context_payload(payload)
        if spec.requires_reading_context and not context["source_text"].strip():
            raise ValueError(f"Agent tool {spec.name} requires selected source text.")

        request_id = max(0, int(payload.get("request_id", 0) or 0))

        if spec.name == "inspect_reading_context":
            return AgentToolExecutionResult(
                tool_name=spec.name,
                output_text=context["source_text"],
                effect=spec.effect,
                request_id=request_id,
                data=context,
            )

        if spec.name == "translate_selection":
            if self._translation_fallback_service is not None:
                result = self._translation_fallback_service.translate(
                    context["source_text"],
                    source_language=context["source_language"],
                    target_language=str(payload.get("target_language", context["target_language"]) or context["target_language"]),
                    request_id=request_id,
                )
                return AgentToolExecutionResult(
                    tool_name=spec.name,
                    output_text=result.translated_text,
                    effect=spec.effect,
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
                context["source_text"],
                source_language=context["source_language"],
                target_language=str(payload.get("target_language", context["target_language"]) or context["target_language"]),
                request_id=request_id,
            )
            return AgentToolExecutionResult(
                tool_name=spec.name,
                output_text=result.translated_text,
                effect=spec.effect,
                provider=result.provider,
                request_id=result.request_id,
                data={
                    "source_language": result.source_language,
                    "target_language": result.target_language,
                },
            )

        quick_action_by_tool = {
            "explain_selection": "reading_explain",
            "summarize_selection": "reading_summarize",
            "analyze_section_role": "reading_section_role",
            "polish_selection": "ai_polish",
        }
        quick_action = quick_action_by_tool.get(spec.name)
        if quick_action:
            result = self._quick_action_service.run(
                action=quick_action,
                **context,
                style=str(payload.get("style", "academic") or "academic"),
                request_id=request_id,
            )
            return AgentToolExecutionResult(
                tool_name=spec.name,
                output_text=result.output_text,
                effect=spec.effect,
                provider=result.provider,
                model=result.model,
                request_id=result.request_id,
                data={"action": result.action},
            )

        if spec.name == "save_research_note":
            result = self._research_note_service.save(
                **context,
                ai_content=str(payload.get("ai_content", "") or ""),
                ai_action=str(payload.get("ai_action", "") or ""),
                user_note=str(payload.get("user_note", "") or ""),
                conversation_id=str(payload.get("conversation_id", "") or ""),
            )
            note = result.note
            return AgentToolExecutionResult(
                tool_name=spec.name,
                output_text=f"Saved research note: {note.display_title}",
                effect=spec.effect,
                request_id=request_id,
                data={
                    "note_id": note.note_id,
                    "created": result.created,
                    "display_title": note.display_title,
                    "excerpt": note.excerpt,
                    "updated_at": note.updated_at,
                    "conversation_id": note.conversation_id,
                },
            )

        raise RuntimeError(f"Agent tool is registered but has no executor: {spec.name}")
