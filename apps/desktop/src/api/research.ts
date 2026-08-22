import { apiDelete, apiGet, apiPatch } from "./client"
import type {
  ResearchNoteDeleteResponse,
  ResearchNoteDetail,
  ResearchSourceProfile,
  ResearchWorkspaceResponse,
} from "./types"

export function getResearchWorkspace(limit = 100): Promise<ResearchWorkspaceResponse> {
  return apiGet<ResearchWorkspaceResponse>(`/api/research/workspace?limit=${limit}`)
}

export function getResearchSource(
  sourceId: string,
  limit = 100,
): Promise<ResearchSourceProfile> {
  return apiGet<ResearchSourceProfile>(
    `/api/research/sources/${encodeURIComponent(sourceId)}?limit=${limit}`,
  )
}

export function getResearchNote(noteId: string): Promise<ResearchNoteDetail> {
  return apiGet<ResearchNoteDetail>(`/api/research/notes/${encodeURIComponent(noteId)}`)
}

export function updateResearchNote(
  noteId: string,
  userNote: string,
): Promise<ResearchNoteDetail> {
  return apiPatch<ResearchNoteDetail, { user_note: string }>(
    `/api/research/notes/${encodeURIComponent(noteId)}`,
    { user_note: userNote },
  )
}

export function deleteResearchNote(noteId: string): Promise<ResearchNoteDeleteResponse> {
  return apiDelete<ResearchNoteDeleteResponse>(
    `/api/research/notes/${encodeURIComponent(noteId)}`,
  )
}
