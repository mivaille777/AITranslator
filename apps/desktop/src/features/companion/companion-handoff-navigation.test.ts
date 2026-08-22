import { describe, expect, it } from "vitest"

import type { CompanionHandoff } from "../../api/types"
import {
  companionConversationPath,
  companionHandoffPath,
} from "./companion-handoff-navigation"

function handoff(conversationId = ""): CompanionHandoff {
  return {
    revision: 3,
    handoff_id: "handoff-3",
    created_at: "2026-08-21T12:00:00Z",
    source_text: "Selected text",
    translated_text: "译文",
    source_language: "en",
    target_language: "zh-CN",
    resource_url: "file:///paper.pdf",
    resource_title: "Paper",
    section_heading: "3. Method",
    context_before: "Before",
    context_after: "After",
    source_kind: "pdf_uia",
    conversation_id: conversationId,
    ai_content: "",
    ai_action: "",
    suggested_prompt: "",
  }
}

describe("companion handoff navigation", () => {
  it("opens an existing overlay conversation directly in the main chat", () => {
    expect(companionHandoffPath(handoff("conversation overlay/7"))).toBe(
      "/chat?conversation=conversation%20overlay%2F7",
    )
  })

  it("uses the same encoded route for native conversation navigation", () => {
    expect(companionConversationPath(" conversation overlay/7 ")).toBe(
      "/chat?conversation=conversation%20overlay%2F7",
    )
  })

  it("keeps context-only handoffs on the normal chat route", () => {
    expect(companionHandoffPath(handoff())).toBe("/chat")
    expect(companionConversationPath("  ")).toBe("/chat")
    expect(companionHandoffPath(null)).toBe("")
  })
})
