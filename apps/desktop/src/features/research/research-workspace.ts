import type { ResearchNoteDetail, ResearchSourceSummary } from "../../api/types"

export interface ResearchFilters {
  query: string
  sourceId: string
  sourceKind: string
}

export function filterResearchNotes(
  notes: ResearchNoteDetail[],
  filters: ResearchFilters,
): ResearchNoteDetail[] {
  const query = filters.query.trim().toLocaleLowerCase()
  return notes.filter((note) => {
    if (filters.sourceId && note.source_id !== filters.sourceId) return false
    if (filters.sourceKind && note.source_kind !== filters.sourceKind) return false
    if (!query) return true
    const haystack = [
      note.display_title,
      note.resource_title,
      note.section_heading,
      note.source_text,
      note.translated_text,
      note.ai_content,
      note.user_note,
      note.resource_url,
    ]
      .join("\n")
      .toLocaleLowerCase()
    return haystack.includes(query)
  })
}

export function researchSourceKinds(sources: ResearchSourceSummary[]): string[] {
  return [...new Set(sources.map((source) => source.source_kind).filter(Boolean))].sort()
}
