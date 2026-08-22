import { describe, expect, it } from "vitest"

import type { ConversationSummary } from "../../api/types"
import { filterConversationHistory, groupConversationHistory } from "./conversation-history"

function conversation(
  id: string,
  updatedAt: string,
  overrides: Partial<ConversationSummary> = {},
): ConversationSummary {
  return {
    conversation_id: id,
    session_id: `session-${id}`,
    title: `Conversation ${id}`,
    created_at: updatedAt,
    updated_at: updatedAt,
    provider: "deepseek",
    model: "deepseek-v4",
    context_mode: "general",
    resource_title: "",
    section_heading: "",
    source_kind: "",
    ...overrides,
  }
}

describe("conversation history utilities", () => {
  it("searches across title and reading metadata", () => {
    const items = [
      conversation("a", "2026-08-21T02:00:00Z", { title: "General planning" }),
      conversation("b", "2026-08-21T03:00:00Z", {
        title: "Paper discussion",
        section_heading: "Gaussian Process localization",
      }),
    ]

    expect(filterConversationHistory(items, "gaussian").map((item) => item.conversation_id)).toEqual(["b"])
    expect(filterConversationHistory(items, "planning").map((item) => item.conversation_id)).toEqual(["a"])
  })

  it("groups conversations using local calendar days", () => {
    const now = new Date(2026, 7, 21, 12, 0, 0)
    const items = [
      conversation("today", new Date(2026, 7, 21, 9, 0, 0).toISOString()),
      conversation("yesterday", new Date(2026, 7, 20, 18, 0, 0).toISOString()),
      conversation("week", new Date(2026, 7, 17, 18, 0, 0).toISOString()),
      conversation("old", new Date(2026, 6, 1, 18, 0, 0).toISOString()),
    ]

    const groups = groupConversationHistory(items, now)
    expect(groups.map((group) => group.label)).toEqual([
      "Today",
      "Yesterday",
      "Previous 7 days",
      "Earlier",
    ])
  })

  it("keeps empty search as a stable no-op", () => {
    const items = [conversation("a", "2026-08-21T02:00:00Z")]
    expect(filterConversationHistory(items, "   ")).toBe(items)
  })
})
