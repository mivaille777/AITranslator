import { AlertTriangle, FileText, LoaderCircle, RefreshCw, Trash2 } from "lucide-react"

import { Badge } from "../../shared/ui/Badge"
import { Button } from "../../shared/ui/Button"
import {
  isKnowledgeDocumentActive,
  knowledgeStatusLabel,
  knowledgeStatusTone,
} from "./knowledge-state"
import type { KnowledgeDocument } from "./knowledge-types"

export default function KnowledgeDocumentRow({
  document,
  deleting,
  reindexing,
  onDelete,
  onReindex,
}: {
  document: KnowledgeDocument
  deleting: boolean
  reindexing: boolean
  onDelete: () => void
  onReindex: () => void
}) {
  const active = isKnowledgeDocumentActive(document.status)

  return (
    <article className="group border-b border-slate-100 px-5 py-4 last:border-b-0 lg:px-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 gap-3.5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[13px] border border-slate-200/80 bg-slate-50 text-slate-500">
            <FileText size={18} strokeWidth={1.7} />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="truncate text-sm font-semibold text-slate-900">
                {document.title || "Untitled document"}
              </h3>
              <Badge tone={knowledgeStatusTone(document.status)}>
                {active && <LoaderCircle size={10} className="mr-1 animate-spin" />}
                {knowledgeStatusLabel(document.status)}
              </Badge>
              <Badge>{document.source_type.toUpperCase()}</Badge>
            </div>
            <p className="mt-1.5 max-w-3xl truncate font-mono text-[10px] text-slate-400">
              {document.source_uri}
            </p>
            <p className="mt-2 text-xs text-slate-500">
              {document.chunk_count > 0 ? `${document.chunk_count} indexed chunks` : "Waiting for indexed chunks"}
              {document.indexed_at && ` · ${new Date(document.indexed_at).toLocaleString()}`}
            </p>

            {document.status === "failed" && (
              <details className="mt-3 max-w-2xl rounded-[13px] border border-rose-100 bg-rose-50/70 px-3 py-2 text-xs text-rose-700">
                <summary className="flex cursor-pointer list-none items-center gap-2 font-semibold">
                  <AlertTriangle size={13} />
                  Indexing failed · show reason
                </summary>
                <p className="mt-2 break-words leading-5">{document.error || "No failure detail was returned."}</p>
              </details>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1 sm:opacity-70 sm:transition-opacity sm:group-hover:opacity-100">
          <Button
            variant="ghost"
            size="xs"
            disabled={active || reindexing || deleting}
            onClick={onReindex}
            aria-label={`Reindex ${document.title}`}
          >
            <RefreshCw size={13} className={reindexing ? "animate-spin" : ""} />
            {reindexing ? "Reindexing…" : "Reindex"}
          </Button>
          <Button
            variant="ghost"
            size="xs"
            disabled={deleting || reindexing}
            onClick={onDelete}
            aria-label={`Delete ${document.title}`}
          >
            <Trash2 size={13} />
            {deleting ? "Deleting…" : "Delete"}
          </Button>
        </div>
      </div>
    </article>
  )
}
