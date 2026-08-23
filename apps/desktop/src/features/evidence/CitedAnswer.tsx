import { BookOpenText } from "lucide-react"
import { useState } from "react"

import { citationSegments, resolveCitation, type ResolvedCitation } from "./citation-model"
import { CitationChip } from "./CitationChip"
import { EvidenceDrawer } from "./EvidenceDrawer"
import type { AgentCitationRef, AgentEvidenceItem } from "./evidence-types"

export function CitedAnswer({
  content,
  evidence,
  citations,
}: {
  content: string
  evidence: AgentEvidenceItem[]
  citations: AgentCitationRef[]
}) {
  const [selected, setSelected] = useState<ResolvedCitation | null>(null)

  return (
    <>
      <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-800">
        {citationSegments(content, citations).map((segment, index) =>
          segment.citation ? (
            <CitationChip
              key={`${segment.citation.citation_id}-${index}`}
              citation={segment.citation}
              onClick={() => setSelected(resolveCitation(segment.citation!, evidence))}
            />
          ) : (
            <span key={`${segment.text}-${index}`}>{segment.text}</span>
          ),
        )}
      </p>

      {citations.length > 0 && (
        <div className="mt-4 border-t border-slate-100 pt-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-500">
            <BookOpenText size={13} />
            Sources
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {citations.map((citation) => {
              const resolved = resolveCitation(citation, evidence)
              const title = resolved.evidence[0]?.title || "Source unavailable"
              return (
                <button
                  key={citation.citation_id}
                  type="button"
                  className="rounded-[11px] border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-left text-[11px] text-slate-600 transition hover:border-cyan-200 hover:bg-cyan-50"
                  onClick={() => setSelected(resolved)}
                >
                  <strong className="mr-1 text-cyan-700">{citation.label}</strong>
                  {title}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {selected && <EvidenceDrawer resolved={selected} onClose={() => setSelected(null)} />}
    </>
  )
}
