// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { desktop } from "../../desktop"
import { CitedAnswer } from "./CitedAnswer"
import { citationSegments, isSafeEvidenceResource } from "./citation-model"
import type { AgentCitationRef, AgentEvidenceItem } from "./evidence-types"

const citation: AgentCitationRef = {
  citation_id: "citation-1",
  evidence_ids: ["evidence:chunk-1"],
  label: "[1]",
}

const evidence: AgentEvidenceItem = {
  evidence_id: "evidence:chunk-1",
  source_type: "knowledge",
  source_id: "document-1",
  title: "Control Systems Paper",
  resource_url: "file:///C:/papers/control.pdf",
  location: "Page 8 · Section Stability",
  excerpt: "The Lyapunov condition bounds the closed-loop response.",
  score: 0.923,
  metadata: {},
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe("RAG citation interaction", () => {
  it("renders verified citation labels as interactive chips", () => {
    render(<CitedAnswer content="The response is bounded [1]." evidence={[evidence]} citations={[citation]} />)

    expect(screen.getByRole("button", { name: "Open citation [1]" })).not.toBeNull()
    expect(citationSegments("Unknown [9]", [citation])).toEqual([
      { text: "Unknown " },
      { text: "[9]" },
    ])
  })

  it("opens citation detail with title, page, section and excerpt", async () => {
    render(<CitedAnswer content="Supported claim [1]" evidence={[evidence]} citations={[citation]} />)

    await userEvent.click(screen.getByRole("button", { name: "Open citation [1]" }))

    expect(screen.getByRole("dialog", { name: "Citation detail [1]" })).not.toBeNull()
    expect(screen.getAllByText("Control Systems Paper")).toHaveLength(2)
    expect(screen.getByText("Page 8 · Section Stability")).not.toBeNull()
    expect(screen.getByText(evidence.excerpt)).not.toBeNull()
  })

  it("opens only a safe local URI supplied by verified evidence", async () => {
    const openSource = vi.spyOn(desktop.files, "openEvidenceSource").mockResolvedValue()
    render(<CitedAnswer content="Supported claim [1]" evidence={[evidence]} citations={[citation]} />)

    await userEvent.click(screen.getByRole("button", { name: "Open citation [1]" }))
    await userEvent.click(screen.getByRole("button", { name: "Open source" }))

    expect(openSource).toHaveBeenCalledWith(evidence.resource_url)
    expect(isSafeEvidenceResource("https://example.org/invented.pdf")).toBe(false)
    expect(isSafeEvidenceResource("file:///C:/papers/control.pdf")).toBe(true)
  })

  it("handles missing and unsafe source evidence without opening it", async () => {
    const openSource = vi.spyOn(desktop.files, "openEvidenceSource").mockResolvedValue()
    const { unmount } = render(
      <CitedAnswer content="Missing source [1]" evidence={[]} citations={[citation]} />,
    )
    await userEvent.click(screen.getByRole("button", { name: "Open citation [1]" }))
    expect(screen.getAllByText("Source unavailable")).toHaveLength(2)
    unmount()

    render(
      <CitedAnswer
        content="Unsafe source [1]"
        evidence={[{ ...evidence, resource_url: "https://example.org/invented.pdf" }]}
        citations={[citation]}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: "Open citation [1]" }))
    expect((screen.getByRole("button", { name: "Open source" }) as HTMLButtonElement).disabled).toBe(true)
    expect(openSource).not.toHaveBeenCalled()
  })
})
