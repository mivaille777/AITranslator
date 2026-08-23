import { ExternalLink, FileQuestion, X } from "lucide-react"
import { useState } from "react"

import { desktop } from "../../desktop"
import { Badge } from "../../shared/ui/Badge"
import { Button } from "../../shared/ui/Button"
import { isSafeEvidenceResource, type ResolvedCitation } from "./citation-model"

export function EvidenceDrawer({
  resolved,
  onClose,
}: {
  resolved: ResolvedCitation
  onClose: () => void
}) {
  const [openError, setOpenError] = useState("")

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/25 backdrop-blur-[2px]" role="presentation" onMouseDown={onClose}>
      <aside
        className="h-full w-full max-w-md overflow-y-auto border-l border-white/60 bg-white/95 p-5 shadow-[-24px_0_70px_rgba(15,23,42,0.18)] backdrop-blur-xl workspace-route-enter"
        role="dialog"
        aria-modal="true"
        aria-label={`Citation detail ${resolved.citation.label}`}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Citation detail</p>
            <h3 className="mt-1.5 text-lg font-semibold text-slate-950">Source {resolved.citation.label}</h3>
          </div>
          <Button variant="ghost" size="xs" aria-label="Close citation detail" onClick={onClose}>
            <X size={16} />
          </Button>
        </header>

        {resolved.evidence.length === 0 ? (
          <div className="mt-8 rounded-[18px] border border-dashed border-slate-200 bg-slate-50 p-6 text-center">
            <FileQuestion size={24} className="mx-auto text-slate-400" />
            <p className="mt-3 text-sm font-semibold text-slate-800">Source unavailable</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              This citation no longer has a matching verified evidence item.
            </p>
          </div>
        ) : (
          <div className="mt-5 space-y-4">
            {resolved.evidence.map((item) => {
              const canOpen = isSafeEvidenceResource(item.resource_url)
              return (
                <section key={item.evidence_id} className="rounded-[18px] border border-slate-200 bg-slate-50/70 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="info">{item.source_type || "evidence"}</Badge>
                    {item.score !== null && <Badge>{item.score.toFixed(3)}</Badge>}
                  </div>
                  <h4 className="mt-3 text-sm font-semibold leading-5 text-slate-900">
                    {item.title || "Untitled source"}
                  </h4>
                  <p className="mt-1 text-xs font-medium text-slate-500">
                    {item.location || "Location unavailable"}
                  </p>
                  <blockquote className="mt-4 border-l-2 border-cyan-300 pl-3 text-sm leading-6 text-slate-600">
                    {item.excerpt || "No excerpt is available."}
                  </blockquote>
                  <Button
                    className="mt-4"
                    size="xs"
                    disabled={!canOpen}
                    onClick={() => {
                      setOpenError("")
                      void desktop.files.openEvidenceSource(item.resource_url).catch((error: unknown) => {
                        setOpenError(error instanceof Error ? error.message : "Unable to open source file.")
                      })
                    }}
                  >
                    <ExternalLink size={13} />
                    Open source
                  </Button>
                  {!canOpen && (
                    <p className="mt-2 text-[11px] leading-5 text-amber-700">
                      Only a verified local file URI from Agent evidence can be opened.
                    </p>
                  )}
                </section>
              )
            })}
          </div>
        )}

        {openError && <p role="alert" className="mt-4 rounded-[13px] bg-rose-50 px-3 py-2 text-xs text-rose-700">{openError}</p>}
      </aside>
    </div>
  )
}
