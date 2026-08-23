import { AlertCircle, FilePlus2, LibraryBig, RefreshCw } from "lucide-react"

import { Button } from "../../shared/ui/Button"
import { EmptyState } from "../../shared/ui/EmptyState"
import KnowledgeDocumentRow from "./KnowledgeDocumentRow"
import type { KnowledgeLibraryController } from "./useKnowledgeLibrary"

export default function KnowledgeLibraryPanel({ library }: { library: KnowledgeLibraryController }) {
  const { documentsQuery, addMutation, deleteMutation, reindexMutation } = library
  const documents = documentsQuery.data?.documents ?? []
  const actionError = addMutation.error ?? deleteMutation.error ?? reindexMutation.error

  if (documentsQuery.isPending) {
    return <KnowledgeLibrarySkeleton />
  }

  return (
    <div className="space-y-4">
      <section className="ait-surface overflow-hidden">
        <header className="flex flex-col gap-4 border-b border-slate-100 px-5 py-5 sm:flex-row sm:items-center sm:justify-between lg:px-7">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Local retrieval
            </p>
            <h2 className="mt-1.5 text-xl font-semibold tracking-tight text-slate-950">
              Knowledge Library
            </h2>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-500">
              Add papers and notes to the local index. Original files remain in place when an index entry is removed.
            </p>
          </div>
          <Button
            variant="primary"
            size="md"
            disabled={addMutation.isPending}
            onClick={() => addMutation.mutate()}
          >
            <FilePlus2 size={16} />
            {addMutation.isPending ? "Adding…" : "Add Document"}
          </Button>
        </header>

        {(documentsQuery.isError || actionError) && (
          <div role="alert" className="m-5 flex items-start gap-3 rounded-[15px] border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-700 lg:mx-7">
            <AlertCircle size={17} className="mt-0.5 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">Knowledge Library action failed</p>
              <p className="mt-1 break-words text-xs leading-5">
                {errorMessage(actionError ?? documentsQuery.error)}
              </p>
            </div>
            {documentsQuery.isError && (
              <Button size="xs" onClick={() => void documentsQuery.refetch()}>
                <RefreshCw size={12} />
                Retry
              </Button>
            )}
          </div>
        )}

        {documents.length === 0 && !documentsQuery.isError ? (
          <div className="p-5 lg:p-7">
            <EmptyState
              icon={<LibraryBig size={25} strokeWidth={1.6} />}
              title="Your local knowledge index is empty"
              description="Import a PDF, DOCX, TXT, Markdown or HTML document. AITranslator will parse, chunk and index it for retrieval."
              actions={(
                <Button variant="primary" disabled={addMutation.isPending} onClick={() => addMutation.mutate()}>
                  <FilePlus2 size={15} />
                  Add your first document
                </Button>
              )}
            />
          </div>
        ) : (
          <div aria-label="Knowledge documents">
            {documents.map((document) => (
              <KnowledgeDocumentRow
                key={document.document_id}
                document={document}
                deleting={deleteMutation.isPending && deleteMutation.variables === document.document_id}
                reindexing={reindexMutation.isPending && reindexMutation.variables === document.document_id}
                onDelete={() => deleteMutation.mutate(document.document_id)}
                onReindex={() => reindexMutation.mutate(document.document_id)}
              />
            ))}
          </div>
        )}
      </section>

      <p className="px-2 text-[11px] leading-5 text-slate-400">
        Supported files: PDF, DOCX, TXT, Markdown and HTML · Documents stay on this device.
      </p>
    </div>
  )
}

function KnowledgeLibrarySkeleton() {
  return (
    <section className="ait-surface overflow-hidden p-7" aria-busy="true" aria-label="Loading Knowledge Library">
      <div className="ait-skeleton h-5 w-40 rounded-full" />
      <div className="ait-skeleton mt-4 h-3 w-[55%] rounded-full" />
      <div className="mt-8 space-y-3">
        <div className="ait-skeleton h-20 rounded-[17px]" />
        <div className="ait-skeleton h-20 rounded-[17px]" />
      </div>
    </section>
  )
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to reach the Knowledge Library API."
}
