import { apiGet, apiPost } from "./client"
import type {
  QuickActionRequest,
  QuickActionResponse,
  QuickActionStatusResponse,
  ResearchNoteListResponse,
  ResearchNoteSaveRequest,
  ResearchNoteSaveResponse,
} from "./types"

export function getQuickActionStatus(): Promise<QuickActionStatusResponse> {
  return apiGet<QuickActionStatusResponse>("/api/quick-actions/status")
}

export function runQuickAction(payload: QuickActionRequest): Promise<QuickActionResponse> {
  return apiPost<QuickActionResponse, QuickActionRequest>("/api/quick-actions/run", payload)
}

export function saveResearchNote(payload: ResearchNoteSaveRequest): Promise<ResearchNoteSaveResponse> {
  return apiPost<ResearchNoteSaveResponse, ResearchNoteSaveRequest>("/api/research/notes", payload)
}

export function listResearchNotes(limit = 5): Promise<ResearchNoteListResponse> {
  return apiGet<ResearchNoteListResponse>(`/api/research/notes?limit=${limit}`)
}
