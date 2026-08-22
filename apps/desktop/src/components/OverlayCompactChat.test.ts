import { describe, expect, it } from "vitest"

import type { OverlayStateResponse, QuickActionResponse } from "../api/types"
import {
  buildOverlayChatHandoff,
  overlayCompanionConversationId,
} from "./overlay-chat-context"

const overlayState: OverlayStateResponse = {
  revision: 4,
  visible: true,
  phase: "ready",
  context_id: "selection-4",
  source_text: "Gaussian processes provide a posterior over the objective.",
  translated_text: "高斯过程提供目标函数的后验分布。",
  source_language: "en",
  target_language: "zh-CN",
  provider: "google_web",
  message: "",
  resource_url: "file:///paper.pdf",
  resource_title: "Control paper",
  section_heading: "3.4 Local refinement",
  context_before: "Previous sentence.",
  context_after: "Next sentence.",
  source_kind: "pdf_uia",
}

const quickResult: QuickActionResponse = {
  action: "reading_explain",
  output_text: "The posterior quantifies uncertainty around the objective.",
  provider: "deepseek",
  model: "deepseek-chat",
  request_id: 8,
}

describe("overlay compact chat context", () => {
  it("preserves the active reading evidence when opening the main chat", () => {
    const handoff = buildOverlayChatHandoff(overlayState, quickResult, "")

    expect(handoff.source_text).toBe(overlayState.source_text)
    expect(handoff.translated_text).toBe(overlayState.translated_text)
    expect(handoff.section_heading).toBe("3.4 Local refinement")
    expect(handoff.conversation_id).toBe("")
    expect(handoff.ai_content).toBe(quickResult.output_text)
    expect(handoff.ai_action).toBe("reading_explain")
  })

  it("uses the latest compact-chat answer as the strongest handoff evidence", () => {
    const handoff = buildOverlayChatHandoff(
      overlayState,
      quickResult,
      "A newer conversational answer.",
    )

    expect(handoff.ai_content).toBe("A newer conversational answer.")
    expect(handoff.ai_action).toBe("conversation_answer")
    expect(handoff.suggested_prompt).toContain("主 AI Chat")
  })

  it("carries the persisted overlay conversation into the main workspace", () => {
    const handoff = buildOverlayChatHandoff(
      overlayState,
      quickResult,
      "A completed compact-chat answer.",
      "  conversation-overlay-42  ",
    )

    expect(handoff.conversation_id).toBe("conversation-overlay-42")
    expect(handoff.ai_content).toBe("A completed compact-chat answer.")
  })

  it("recovers the persisted conversation ID from overlay backend state", () => {
    const stateWithConversation = {
      ...overlayState,
      companion_conversation_id: "  conversation-overlay-42  ",
    }

    expect(overlayCompanionConversationId(stateWithConversation)).toBe(
      "conversation-overlay-42",
    )
    expect(overlayCompanionConversationId(overlayState)).toBe("")
  })
})
