import { useQuery } from "@tanstack/react-query"
import { BookCopy, Database, Layers3, NotebookTabs } from "lucide-react"

import { listKnowledgeDocuments } from "../knowledge/knowledge-api"
import type { TranslationWorkspaceController } from "../translation/useTranslationWorkspace"
import { getResearchWorkspace } from "../../api/research"
import { queryKeys } from "../../shared/query/query-keys"

const SCOPE_SOURCE_LIMIT = 100

export default function ResearchScopePanel({
  workspace,
}: {
  workspace: TranslationWorkspaceController
}) {
  const documentsQuery = useQuery({
    queryKey: queryKeys.knowledge.documents,
    queryFn: listKnowledgeDocuments,
  })
  const researchQuery = useQuery({
    queryKey: queryKeys.research.workspace(SCOPE_SOURCE_LIMIT),
    queryFn: () => getResearchWorkspace(SCOPE_SOURCE_LIMIT),
  })

  const scope = workspace.researchRetrievalScope
  const readyDocuments = (documentsQuery.data?.documents ?? []).filter(
    (document) => document.status === "ready",
  )
  const sources = researchQuery.data?.sources ?? []

  function toggleDocument(documentId: string) {
    const current = new Set(scope.knowledgeDocumentIds)
    if (current.has(documentId)) current.delete(documentId)
    else current.add(documentId)
    workspace.setResearchRetrievalScope({
      knowledgeDocumentIds: [...current],
      researchSourceIds: scope.researchSourceIds,
    })
  }

  function toggleResearchSource(sourceId: string) {
    const current = new Set(scope.researchSourceIds)
    if (current.has(sourceId)) current.delete(sourceId)
    else current.add(sourceId)
    workspace.setResearchRetrievalScope({
      knowledgeDocumentIds: scope.knowledgeDocumentIds,
      researchSourceIds: [...current],
    })
  }

  function clearScope() {
    workspace.setResearchRetrievalScope({
      knowledgeDocumentIds: [],
      researchSourceIds: [],
    })
  }

  const scoped = scope.knowledgeDocumentIds.length > 0 || scope.researchSourceIds.length > 0

  return (
    <section className="ait-surface overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200/70 px-5 py-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-500">
            <Layers3 size={17} />
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.17em] text-slate-400">
              Trusted research scope
            </p>
            <h2 className="mt-1 text-sm font-semibold text-slate-900">
              Bound Agent retrieval to selected evidence sources
            </h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Empty selection means global scope. Selected IDs come from the workspace, not from LLM-generated Tool arguments.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={clearScope}
          disabled={!scoped}
          className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Use global scope
        </button>
      </div>

      <div className="grid gap-0 lg:grid-cols-2">
        <ScopeColumn
          icon={<Database size={14} />}
          title="Indexed documents"
          description="Constrains search_knowledge_base and cross-document comparison."
          emptyText={documentsQuery.isPending ? "Loading indexed documents…" : "No ready indexed documents."}
          items={readyDocuments.map((document) => ({
            id: document.document_id,
            title: document.title || "Untitled document",
            meta: `${document.source_type} · ${document.chunk_count} chunks`,
            selected: scope.knowledgeDocumentIds.includes(document.document_id),
          }))}
          onToggle={toggleDocument}
        />
        <ScopeColumn
          icon={<NotebookTabs size={14} />}
          title="Research memory sources"
          description="Constrains search_research_notes over saved evidence and annotations."
          emptyText={researchQuery.isPending ? "Loading research sources…" : "No saved research sources."}
          items={sources.map((source) => ({
            id: source.source_id,
            title: source.display_title,
            meta: `${source.note_count} notes · ${source.section_count} sections`,
            selected: scope.researchSourceIds.includes(source.source_id),
          }))}
          onToggle={toggleResearchSource}
          bordered
        />
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-slate-200/70 bg-slate-50/55 px-5 py-3 text-[11px] text-slate-500">
        <BookCopy size={13} />
        <span>
          Document scope: {scope.knowledgeDocumentIds.length || "all"} · Research-memory scope: {scope.researchSourceIds.length || "all"}
        </span>
      </div>
    </section>
  )
}

function ScopeColumn({
  icon,
  title,
  description,
  emptyText,
  items,
  onToggle,
  bordered = false,
}: {
  icon: React.ReactNode
  title: string
  description: string
  emptyText: string
  items: Array<{ id: string; title: string; meta: string; selected: boolean }>
  onToggle: (id: string) => void
  bordered?: boolean
}) {
  return (
    <div className={`p-4 ${bordered ? "border-t border-slate-200/70 lg:border-l lg:border-t-0" : ""}`}>
      <div className="flex items-center gap-2 text-slate-600">
        {icon}
        <p className="text-xs font-semibold">{title}</p>
      </div>
      <p className="mt-1 text-[11px] leading-5 text-slate-400">{description}</p>
      <div className="mt-3 max-h-40 space-y-1.5 overflow-y-auto pr-1">
        {items.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-200 px-3 py-2 text-[11px] text-slate-400">
            {emptyText}
          </p>
        ) : (
          items.map((item) => (
            <label
              key={item.id}
              className={`flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2 transition ${
                item.selected
                  ? "border-cyan-200 bg-cyan-50/70"
                  : "border-slate-200/70 bg-white hover:border-slate-300"
              }`}
            >
              <input
                type="checkbox"
                checked={item.selected}
                onChange={() => onToggle(item.id)}
                className="mt-0.5"
              />
              <span className="min-w-0">
                <span className="block truncate text-[11px] font-medium text-slate-700">{item.title}</span>
                <span className="mt-0.5 block text-[10px] text-slate-400">{item.meta}</span>
              </span>
            </label>
          ))
        )}
      </div>
    </div>
  )
}
