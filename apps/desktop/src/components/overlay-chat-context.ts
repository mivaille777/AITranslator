import type {
  CompanionHandoffRequest,
  OverlayStateResponse,
  QuickActionResponse,
} from "../api/types"
import type { CompanionContextSnapshot } from "../features/companion/companion-runtime"

export function contextFromOverlay(
  state: OverlayStateResponse,
  aiResult: QuickActionResponse | null,
): CompanionContextSnapshot {
  return {
    source_text: state.source_text,
    translated_text: state.translated_text,
    source_language: state.source_language,
    target_language: state.target_language,
    resource_url: state.resource_url,
    resource_title: state.resource_title,
    section_heading: state.section_heading,
    context_before: state.context_before,
    context_after: state.context_after,
    source_kind: state.source_kind || "desktop",
    ai_content: aiResult?.output_text ?? "",
    ai_action: aiResult?.action ?? "",
  }
}

export function buildOverlayChatHandoff(
  state: OverlayStateResponse,
  aiResult: QuickActionResponse | null,
  latestAssistantText: string,
): CompanionHandoffRequest {
  return {
    source_text: state.source_text,
    translated_text: state.translated_text,
    source_language: state.source_language,
    target_language: state.target_language,
    resource_url: state.resource_url,
    resource_title: state.resource_title,
    section_heading: state.section_heading,
    context_before: state.context_before,
    context_after: state.context_after,
    source_kind: state.source_kind || "desktop",
    ai_content: latestAssistantText || aiResult?.output_text || "",
    ai_action: latestAssistantText ? "conversation_answer" : aiResult?.action || "",
    suggested_prompt: latestAssistantText
      ? "请在主 AI Chat 中继续基于当前阅读上下文分析。"
      : aiResult
        ? "请基于当前划词内容、译文和已有 AI 结果继续分析。"
        : "请基于当前阅读上下文继续分析。",
  }
}
