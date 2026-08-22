import { describe, expect, it } from "vitest"

import type { ConversationDetail } from "../../api/types"
import { projectPersistedContext } from "./context-persistence-policy"
import type { CompanionContextSnapshot } from "./companion-runtime"

function conversation(): ConversationDetail {
  return {
    conversation_id: "conversation-1",
    session_id: "session-1",
    title: "Existing conversation",
    created_at: "2026-08-22T00:00:00Z",
    updated_at: "2026-08-22T00:00:01Z",
    provider: "deepseek",
    model: "deepseek-v4-pro",
    context_mode: "reading",
    resource_title: "Server title",
    section_heading: "",
    source_kind: "browser",
    resource_url: "https://example.com/server",
    source_text: "server selection",
    translated_text: "",
    source_language: "auto",
    target_language: "zh-CN",
    context_before: "",
    context_after: "",
    messages: [],
  }
}

describe("context-only persistence policy", () => {
  it("keeps the newest local reading context projection without owning composer state", () => {
    const preferred: CompanionContextSnapshot = {
      source_text: "latest mouse selection",
      translated_text: "",
      source_language: "auto",
      target_language: "zh-CN",
      resource_url: "https://chatgpt.com/current",
      resource_title: "Current page",
      application: "chrome.exe",
      section_heading: "",
      context_before: "before",
      context_after: "after",
      source_kind: "browser",
    }

    const projected = projectPersistedContext(conversation(), preferred)

    expect(projected.context.source_text).toBe("latest mouse selection")
    expect(projected.context.application).toBe("chrome.exe")
    expect(projected.context.resource_title).toBe("Current page")
    expect(projected.contextMode).toBe("reading")
    expect(projected).not.toHaveProperty("draft")
    expect(projected).not.toHaveProperty("messages")
  })
})
