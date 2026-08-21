import { describe, expect, it } from "vitest"

import type { ResearchNoteDetail, ResearchSourceSummary } from "../../api/types"
import { filterResearchNotes, researchSourceKinds } from "./research-workspace"

function note(overrides: Partial<ResearchNoteDetail> = {}): ResearchNoteDetail {
  return {
    note_id: "n1",
    source_id: "s1",
    created_at: "2026-08-21T00:00:00Z",
    updated_at: "2026-08-21T00:00:00Z",
    display_title: "Paper A",
    excerpt: "Gaussian process anchor",
    resource_url: "https://example.org/a",
    resource_title: "Paper A",
    section_heading: "Method",
    source_text: "Gaussian process anchor",
    translated_text: "高斯过程锚点",
    context_before: "before",
    context_after: "after",
    source_kind: "browser_selection",
    ai_content: "Explanation",
    ai_action: "reading_explain",
    user_note: "Important mechanism",
    conversation_id: "c1",
    ...overrides,
  }
}

describe("research workspace filters", () => {
  it("filters by source and source kind", () => {
    const notes = [note(), note({ note_id: "n2", source_id: "s2", source_kind: "pdf", resource_title: "Paper B" })]
    expect(filterResearchNotes(notes, { query: "", sourceId: "s2", sourceKind: "pdf" })).toHaveLength(1)
  })

  it("searches user annotations and evidence text", () => {
    const notes = [note(), note({ note_id: "n2", user_note: "", source_text: "Actuator delay" })]
    expect(filterResearchNotes(notes, { query: "mechanism", sourceId: "", sourceKind: "" })[0]?.note_id).toBe("n1")
    expect(filterResearchNotes(notes, { query: "actuator", sourceId: "", sourceKind: "" })[0]?.note_id).toBe("n2")
  })

  it("returns unique sorted source kinds", () => {
    const sources = [
      { source_id: "1", display_title: "A", resource_url: "", source_kind: "pdf", note_count: 1, linked_conversation_count: 0, updated_at: "" },
      { source_id: "2", display_title: "B", resource_url: "", source_kind: "browser_selection", note_count: 1, linked_conversation_count: 0, updated_at: "" },
      { source_id: "3", display_title: "C", resource_url: "", source_kind: "pdf", note_count: 1, linked_conversation_count: 0, updated_at: "" },
    ] satisfies ResearchSourceSummary[]
    expect(researchSourceKinds(sources)).toEqual(["browser_selection", "pdf"])
  })
})
