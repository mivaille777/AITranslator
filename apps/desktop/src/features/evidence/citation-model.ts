import type { AgentCitationRef, AgentEvidenceItem } from "./evidence-types"

export interface ResolvedCitation {
  citation: AgentCitationRef
  evidence: AgentEvidenceItem[]
}

export function resolveCitation(
  citation: AgentCitationRef,
  evidence: AgentEvidenceItem[],
): ResolvedCitation {
  const byId = new Map(evidence.map((item) => [item.evidence_id, item]))
  return {
    citation,
    evidence: citation.evidence_ids.flatMap((id) => {
      const item = byId.get(id)
      return item ? [item] : []
    }),
  }
}

export function isSafeEvidenceResource(resourceUrl: string): boolean {
  try {
    const parsed = new URL(resourceUrl)
    return parsed.protocol === "file:" && parsed.pathname.length > 1
  } catch {
    return false
  }
}

export function citationSegments(content: string, citations: AgentCitationRef[]): Array<{
  text: string
  citation?: AgentCitationRef
}> {
  const citationByLabel = new Map(citations.map((citation) => [citation.label, citation]))
  const segments: Array<{ text: string; citation?: AgentCitationRef }> = []
  let cursor = 0

  for (const match of content.matchAll(/\[\d+\]/g)) {
    const index = match.index ?? 0
    if (index > cursor) segments.push({ text: content.slice(cursor, index) })
    const label = match[0]
    const citation = citationByLabel.get(label)
    segments.push(citation ? { text: label, citation } : { text: label })
    cursor = index + label.length
  }
  if (cursor < content.length) segments.push({ text: content.slice(cursor) })
  return segments
}
