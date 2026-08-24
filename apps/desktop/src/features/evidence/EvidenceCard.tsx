import { ExternalLink } from "lucide-react"
import { Link } from "react-router-dom"

import { desktop } from "../../desktop"
import { Badge } from "../../shared/ui/Badge"
import { Button } from "../../shared/ui/Button"
import { buttonClassName } from "../../shared/ui/button-styles"
import { evidenceNavigation, isSafeEvidenceResource } from "./citation-model"
import type { AgentEvidenceItem } from "./evidence-types"

export function EvidenceCard({
  item,
  compact = false,
  onOpenError,
}: {
  item: AgentEvidenceItem
  compact?: boolean
  onOpenError?: (message: string) => void
}) {
  const canOpen = isSafeEvidenceResource(item.resource_url)
  const navigation = evidenceNavigation(item)

  return (
    <article className={`rounded-[18px] border border-slate-200 bg-slate-50/70 ${compact ? "p-3" : "p-4"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="info">{item.source_type || "evidence"}</Badge>
        <Badge tone="success">Relevant source</Badge>
      </div>
      <h4 className="mt-3 text-sm font-semibold leading-5 text-slate-900">
        {item.title || "Untitled source"}
      </h4>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {navigation.pageNumber && <Badge>Page {navigation.pageNumber}</Badge>}
        {navigation.sectionHeading && <Badge>{navigation.sectionHeading}</Badge>}
        {!navigation.pageNumber && !navigation.sectionHeading && <span className="text-xs font-medium text-slate-500">{item.location || "Location unavailable"}</span>}
      </div>
      <blockquote className={`${compact ? "line-clamp-3" : ""} mt-4 border-l-2 border-cyan-300 pl-3 text-sm leading-6 text-slate-600`}>
        {item.excerpt || "No excerpt is available."}
      </blockquote>
      {!compact && (
        <>
          <Button
            className="mt-4"
            size="xs"
            disabled={!canOpen}
            onClick={() => {
              onOpenError?.("")
              void desktop.files.openEvidenceSource(item.resource_url).catch((error: unknown) => {
                onOpenError?.(error instanceof Error ? error.message : "Unable to open source file.")
              })
            }}
          >
            <ExternalLink size={13} />
            Open document
          </Button>
          {navigation.knowledgeDocumentId && (
            <Link
              className={buttonClassName({ size: "xs", variant: "ghost", className: "mt-4 ml-2" })}
              to={`/knowledge?document=${encodeURIComponent(navigation.knowledgeDocumentId)}`}
            >
              Knowledge details
            </Link>
          )}
          {!canOpen && (
            <p className="mt-2 text-[11px] leading-5 text-amber-700">
              Only a verified local file URI from retrieved evidence can be opened.
            </p>
          )}
        </>
      )}
    </article>
  )
}
