import { apiGet } from "./client"

export interface ReadingSelection {
  selection_id: string
  text: string
  provider: string
  source_kind: string
  resource_url: string
  resource_title: string
  local_locator: string
  application: string
  page_number: number | null
  section_heading: string
  context_before: string
  context_after: string
}

export interface ReadingSelectionEnvelope {
  selection: ReadingSelection | null
}

let latestReadingSelection: ReadingSelection | null = null

export async function getReadingSelection(): Promise<ReadingSelectionEnvelope> {
  const envelope = await apiGet<ReadingSelectionEnvelope>("/api/reading/selection")
  latestReadingSelection = envelope.selection
  return envelope
}

export function getCachedReadingSelection(): ReadingSelection | null {
  return latestReadingSelection
}
