import { AlertCircle, FilePlus2, LibraryBig, RefreshCw, Search } from "lucide-react"
import { useState } from "react"
import { useSearchParams } from "react-router-dom"

import { desktop } from "../../desktop"
import { Button } from "../../shared/ui/Button"
import { EmptyState } from "../../shared/ui/EmptyState"
import { KnowledgeDeleteDialog } from "./KnowledgeDeleteDialog"
import { KnowledgeDocumentDetail } from "./KnowledgeDocumentDetail"
import KnowledgeDocumentRow from "./KnowledgeDocumentRow"
import { KnowledgeImportDialog } from "./KnowledgeImportDialog"
import { KnowledgeRuntimeCard } from "./KnowledgeRuntimeCard"
import type { KnowledgeDocument } from "./knowledge-types"
import type { KnowledgeLibraryController } from "./useKnowledgeLibrary"

type DocumentFilter = "all" | "pdf" | "docx" | "notes"

export default function KnowledgeLibraryPanel({ library }: { library: KnowledgeLibraryController }) {
  const { documentsQuery, runtimeQuery, addMutation, deleteMutation, reindexMutation } = library
  const [searchParams, setSearchParams] = useSearchParams()
  const documents = documentsQuery.data?.documents ?? []
  const [search, setSearch] = useState("")
  const [filter, setFilter] = useState<DocumentFilter>("all")
  const [importOpen, setImportOpen] = useState(false)
  const [selected, setSelected] = useState<KnowledgeDocument | null>(null)
  const [removeTarget, setRemoveTarget] = useState<KnowledgeDocument | null>(null)
  const [openError, setOpenError] = useState("")
  const actionError = addMutation.error ?? deleteMutation.error ?? reindexMutation.error
  const requestedDocument = documents.find((document) => document.document_id === searchParams.get("document")) ?? null
  const activeDocument = selected ?? requestedDocument

  function closeDocumentDetail() {
    setSelected(null)
    if (!searchParams.has("document")) return
    const next = new URLSearchParams(searchParams)
    next.delete("document")
    setSearchParams(next, { replace: true })
  }

  const visibleDocuments = (() => {
    const normalized = search.trim().toLocaleLowerCase()
    return documents.filter((document) => {
      const matchesSearch = !normalized || [document.title, document.source_uri, document.source_type]
        .join(" ").toLocaleLowerCase().includes(normalized)
      const type = document.source_type.toLocaleLowerCase()
      const matchesType = filter === "all" || type === filter || (filter === "notes" && ["txt", "md", "html"].includes(type))
      return matchesSearch && matchesType
    })
  })()

  if (documentsQuery.isPending) return <KnowledgeLibrarySkeleton />

  return (
    <div className="space-y-4">
      <section className="ait-surface overflow-hidden">
        <header className="flex flex-col gap-4 border-b border-slate-100 px-5 py-5 sm:flex-row sm:items-center sm:justify-between lg:px-7">
          <div><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Local retrieval</p><h2 className="mt-1.5 text-xl font-semibold tracking-tight text-slate-950">Knowledge Base</h2><p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-500">Build a local evidence library that AI Chat and Agent Workspace can retrieve from.</p></div>
          <Button variant="primary" size="md" disabled={addMutation.isPending} onClick={() => setImportOpen(true)}><FilePlus2 size={16} />Add documents</Button>
        </header>

        {runtimeQuery.data ? <KnowledgeRuntimeCard runtime={runtimeQuery.data} /> : runtimeQuery.isError ? <div className="border-b border-amber-100 bg-amber-50/60 px-5 py-3 text-xs text-amber-700 lg:px-7">Runtime summary is unavailable. Document management remains available.</div> : null}

        {(documentsQuery.isError || actionError || openError) && (
          <div role="alert" className="m-5 flex items-start gap-3 rounded-[15px] border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-700 lg:mx-7"><AlertCircle size={17} className="mt-0.5 shrink-0" /><div className="min-w-0 flex-1"><p className="font-semibold">Knowledge Library action failed</p><p className="mt-1 break-words text-xs leading-5">{openError || errorMessage(actionError ?? documentsQuery.error)}</p></div>{documentsQuery.isError && <Button size="xs" onClick={() => void documentsQuery.refetch()}><RefreshCw size={12} />Retry</Button>}</div>
        )}

        {documents.length > 0 && (
          <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-3 sm:flex-row sm:items-center sm:justify-between lg:px-7">
            <label className="flex min-w-0 flex-1 items-center gap-2 rounded-[13px] border border-slate-200 bg-white px-3 py-2 sm:max-w-md"><Search size={14} className="text-slate-400" /><input className="min-w-0 flex-1 bg-transparent text-xs text-slate-700 outline-none placeholder:text-slate-400" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search documents…" /></label>
            <div className="flex rounded-[12px] bg-slate-100 p-1" aria-label="Document type filter">{(["all", "pdf", "docx", "notes"] as const).map((value) => <button key={value} type="button" className={`rounded-[9px] px-2.5 py-1.5 text-[10px] font-medium capitalize ${filter === value ? "bg-white text-slate-800 shadow-sm" : "text-slate-500"}`} onClick={() => setFilter(value)}>{value}</button>)}</div>
          </div>
        )}

        {documents.length === 0 && !documentsQuery.isError ? (
          <div className="p-5 lg:p-7"><EmptyState icon={<LibraryBig size={25} strokeWidth={1.6} />} title="Build your knowledge base" description="Add papers, documents, and notes so AITrans can retrieve evidence while you read and ask questions." actions={<Button variant="primary" disabled={addMutation.isPending} onClick={() => setImportOpen(true)}><FilePlus2 size={15} />Add documents</Button>} /></div>
        ) : visibleDocuments.length === 0 ? (
          <div className="p-7"><EmptyState title="No documents match this filter" description="Try a different search term or document type." /></div>
        ) : (
          <div className="ait-scroll-panel max-h-[min(58vh,680px)] overflow-y-auto overscroll-contain" aria-label="Knowledge documents">
            {visibleDocuments.map((document) => <KnowledgeDocumentRow key={document.document_id} document={document} deleting={deleteMutation.isPending && deleteMutation.variables === document.document_id} reindexing={reindexMutation.isPending && reindexMutation.variables === document.document_id} onOpen={() => setSelected(document)} onReveal={() => { setOpenError(""); void desktop.files.openEvidenceSource(document.source_uri).catch((error: unknown) => setOpenError(errorMessage(error))) }} onRemove={() => setRemoveTarget(document)} onReindex={() => reindexMutation.mutate(document.document_id)} />)}
          </div>
        )}
      </section>

      <p className="px-2 text-[11px] leading-5 text-slate-400">Supported files: PDF, DOCX, TXT, Markdown and HTML · Documents and models stay on this device.</p>
      <KnowledgeImportDialog open={importOpen} adding={addMutation.isPending} onClose={() => !addMutation.isPending && setImportOpen(false)} onBrowse={() => addMutation.mutate(undefined, { onSuccess: (result) => { if (result) setImportOpen(false) } })} />
      {activeDocument && <KnowledgeDocumentDetail document={activeDocument} reindexing={reindexMutation.isPending && reindexMutation.variables === activeDocument.document_id} onClose={closeDocumentDetail} onReindex={() => reindexMutation.mutate(activeDocument.document_id)} onRemove={() => setRemoveTarget(activeDocument)} />}
      <KnowledgeDeleteDialog document={removeTarget} deleting={deleteMutation.isPending} onCancel={() => !deleteMutation.isPending && setRemoveTarget(null)} onConfirm={() => removeTarget && deleteMutation.mutate(removeTarget.document_id, { onSuccess: () => { if (activeDocument?.document_id === removeTarget.document_id) closeDocumentDetail(); setRemoveTarget(null) } })} />
    </div>
  )
}

function KnowledgeLibrarySkeleton() {
  return <section className="ait-surface overflow-hidden p-7" aria-busy="true" aria-label="Loading Knowledge Library"><div className="ait-skeleton h-5 w-40 rounded-full" /><div className="ait-skeleton mt-4 h-3 w-[55%] rounded-full" /><div className="mt-8 grid gap-3 sm:grid-cols-3"><div className="ait-skeleton h-24 rounded-[17px]" /><div className="ait-skeleton h-24 rounded-[17px]" /><div className="ait-skeleton h-24 rounded-[17px]" /></div></section>
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to reach the Knowledge Library API."
}
