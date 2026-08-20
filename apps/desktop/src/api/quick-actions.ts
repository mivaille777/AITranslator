import { apiGet, apiPost } from "./client"
import type {
  QuickActionRequest,
  QuickActionResponse,
  QuickActionStatusResponse,
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
