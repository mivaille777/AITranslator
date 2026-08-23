import { useState } from "react"

import { citationSegments, resolveCitation, type ResolvedCitation } from "./citation-model"
import { CitationChip } from "./CitationChip"
import { CitationGroup } from "./CitationGroup"
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
              evidence={resolveCitation(segment.citation, evidence).evidence[0]}
              onClick={() => setSelected(resolveCitation(segment.citation!, evidence))}
            />
          ) : (
            <span key={`${segment.text}-${index}`}>{segment.text}</span>
          ),
        )}
      </p>

      <CitationGroup evidence={evidence} citations={citations} onSelect={setSelected} />

      {selected && <EvidenceDrawer resolved={selected} onClose={() => setSelected(null)} />}
    </>
  )
}
