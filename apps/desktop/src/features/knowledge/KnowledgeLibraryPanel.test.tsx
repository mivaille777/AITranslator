// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { desktop } from "../../desktop"
import KnowledgeLibraryPanel from "./KnowledgeLibraryPanel"
import type { KnowledgeDocument, KnowledgeDocumentStatus } from "./knowledge-types"
import { useKnowledgeLibrary } from "./useKnowledgeLibrary"

const fetchMock = vi.fn<typeof fetch>()

function document(status: KnowledgeDocumentStatus, overrides: Partial<KnowledgeDocument> = {}): KnowledgeDocument {
  return {
    document_id: `doc-${status}`,
    title: `${status} paper.pdf`,
    source_uri: `file:///C:/papers/${status}.pdf`,
    source_type: "pdf",
    status,
    chunk_count: status === "ready" ? 12 : 0,
    indexed_at: status === "ready" ? "2026-08-24T00:00:00Z" : null,
    error: "",
    content_hash: "hash",
    parser_version: "basic@1",
    chunker_version: "structure@1",
    embedding_model: "qwen3",
    embedding_dimension: 1024,
    ...overrides,
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

function runtime(documentCount = 1) {
  return { enabled: true, embedding_provider: "qwen3", embedding_model: "Qwen3-Embedding-0.6B", embedding_status: "ready", device: "cuda", dimension: 1024, vector_store_provider: "qdrant", collection_name: "knowledge", document_count: documentCount, ready_document_count: documentCount, indexed_chunk_count: documentCount * 12, max_file_bytes: 1 }
}

function renderLibrary(initialEntries = ["/knowledge"]) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <QueryClientProvider client={client}>
        <LibraryHarness />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

function LibraryHarness() {
  return <KnowledgeLibraryPanel library={useKnowledgeLibrary()} />
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock)
  vi.spyOn(desktop.files, "pickKnowledgeDocument").mockResolvedValue("C:\\papers\\new.pdf")
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  fetchMock.mockReset()
})

describe("Knowledge Library", () => {
  it("loads documents and renders pending, indexing, ready and failed states", async () => {
    fetchMock.mockImplementation(async (input) => String(input).endsWith("/runtime")
      ? jsonResponse(runtime(4))
      : jsonResponse({ total: 4, documents: [document("pending"), document("indexing"), document("ready"), document("failed", { error: "The PDF parser could not read page 3." })] }))

    renderLibrary()

    expect(await screen.findByText("Pending")).not.toBeNull()
    expect(screen.getByText("Indexing")).not.toBeNull()
    expect(screen.getByText("Ready")).not.toBeNull()
    expect(screen.getByText("Failed")).not.toBeNull()
    expect(screen.getByText("The PDF parser could not read page 3.")).not.toBeNull()
  })

  it("adds a selected document and refreshes the shared list", async () => {
    fetchMock.mockImplementation(async (_input, init) => {
      if (String(_input).endsWith("/runtime")) return jsonResponse(runtime(0))
      if (init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({ path: "C:\\papers\\new.pdf" })
        return jsonResponse({ document: document("ready"), reused_existing: false, elapsed_ms: 12 }, 201)
      }
      return jsonResponse({ total: 0, documents: [] })
    })

    renderLibrary()
    await userEvent.click(await screen.findByRole("button", { name: "Add documents" }))
    await userEvent.click(screen.getByRole("button", { name: "Browse files" }))

    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true))
    expect(desktop.files.pickKnowledgeDocument).toHaveBeenCalledOnce()
  })

  it("deletes an index entry without targeting the source file", async () => {
    fetchMock.mockImplementation(async (input, init) => {
      if (String(input).endsWith("/runtime")) return jsonResponse(runtime())
      if (init?.method === "DELETE") {
        expect(String(input)).toContain("/api/knowledge/documents/doc-ready")
        return jsonResponse({ document_id: "doc-ready", deleted: true, source_file_preserved: true })
      }
      return jsonResponse({ total: 1, documents: [document("ready")] })
    })

    renderLibrary()
    await userEvent.click(await screen.findByLabelText("More actions for ready paper.pdf"))
    await userEvent.click(screen.getByRole("button", { name: "Remove" }))
    await userEvent.click(within(screen.getByRole("alertdialog", { name: "Remove from Knowledge Base" })).getByRole("button", { name: "Remove" }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(true))
  })

  it("reindexes a ready document", async () => {
    fetchMock.mockImplementation(async (input, init) => {
      if (String(input).endsWith("/runtime")) return jsonResponse(runtime())
      if (init?.method === "POST" && String(input).endsWith("/reindex")) {
        return jsonResponse({ document: document("indexing"), reused_existing: false, elapsed_ms: 3 })
      }
      return jsonResponse({ total: 1, documents: [document("ready")] })
    })

    renderLibrary()
    await userEvent.click(await screen.findByRole("button", { name: "Reindex ready paper.pdf" }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/reindex"))).toBe(true))
  })

  it("renders API errors and allows retry", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Knowledge runtime unavailable." }, 503))

    renderLibrary()

    expect(await screen.findByRole("alert")).not.toBeNull()
    expect(screen.getByText("Knowledge runtime unavailable.")).not.toBeNull()
    expect(screen.getByRole("button", { name: "Retry" })).not.toBeNull()
  })

  it("opens a document detail drawer from a citation navigation target", async () => {
    fetchMock.mockImplementation(async (input) => String(input).endsWith("/runtime")
      ? jsonResponse(runtime())
      : jsonResponse({ total: 1, documents: [document("ready")] }))

    renderLibrary(["/knowledge?document=doc-ready"])

    expect(await screen.findByRole("dialog", { name: "Document details ready paper.pdf" })).not.toBeNull()
    expect(screen.getByText(/512 target tokens · 80 overlap/)).not.toBeNull()
  })
})
