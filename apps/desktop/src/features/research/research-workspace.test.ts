import { describe, expect, it } from "vitest"

import type { ResearchNoteDetail, ResearchSourceSummary } from "../../api/types"
import {
  filterResearchNotes,
  researchSourceFamilies,
  researchSourceKinds,
} from "./research-workspace"

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

function source(overrides: Partial<ResearchSourceSummary> = {}): ResearchSourceSummary {
  return {
    source_id: "s1",
    display_title: "Paper A",
    resource_url: "https://example.org/a",
    resource_locator: "https://example.org/a",
    source_kind: "browser_selection",
    source_family: "browser",
    identity_quality: "locator",
    note_count: 1,
    section_count: 1,
    linked_conversation_count: 0,
    annotation_count: 0,
    ai_evidence_count: 0,
    updated_at: "2026-08-21T00:00:00Z",
    ...overrides,
  }
}

describe("research workspace filters", () => {
  it("filters by source and source kind", () => {
    const notes = [
      note(),
      note({ note_id: "n2", source_id: "s2", source_kind: "pdf", resource_title: "Paper B" }),
    ]
    expect(
      filterResearchNotes(notes, {
        query: "",
        sourceId: "s2",
        sourceKind: "pdf",
      }),
    ).toHaveLength(1)
  })

  it("filters represented sections without inventing an outline", () => {
    const notes = [
      note({ note_id: "method", section_heading: "Method" }),
      note({ note_id: "results", section_heading: "Results" }),
      note({ note_id: "none", section_heading: "" }),
    ]
    expect(
      filterResearchNotes(notes, {
        query: "",
        sourceId: "",
        sourceKind: "",
        sectionHeading: "Results",
      }).map((item) => item.note_id),
    ).toEqual(["results"])
    expect(
      filterResearchNotes(notes, {
        query: "",
        sourceId: "",
        sourceKind: "",
        sectionHeading: "Unsectioned evidence",
      }).map((item) => item.note_id),
    ).toEqual(["none"])
  })

  it("searches user annotations and evidence text", () => {
    const notes = [
      note(),
      note({ note_id: "n2", user_note: "", source_text: "Actuator delay" }),
    ]
    expect(filterResearchNotes(notes, { query: "mechanism", sourceId: "", sourceKind: "" })[0]?.note_id).toBe("n1")
    expect(filterResearchNotes(notes, { query: "actuator", sourceId: "", sourceKind: "" })[0]?.note_id).toBe("n2")
  })

  it("returns unique sorted source kinds and normalized families", () => {
    const sources = [
      source({ source_id: "1", source_kind: "pdf", source_family: "pdf" }),
      source({ source_id: "2", source_kind: "browser_selection", source_family: "browser" }),
      source({ source_id: "3", source_kind: "pdf", source_family: "pdf" }),
    ] satisfies ResearchSourceSummary[]
    expect(researchSourceKinds(sources)).toEqual(["browser_selection", "pdf"])
    expect(researchSourceFamilies(sources)).toEqual(["browser", "pdf"])
  })
})
