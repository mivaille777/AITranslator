import { apiGet, apiPost } from "./client"
import type {
  CompanionChatRequest,
  CompanionChatResponse,
  CompanionChatStatusResponse,
  CompanionHandoff,
  CompanionHandoffEnvelope,
  CompanionHandoffRequest,
} from "./types"

export type CompanionClientSurface = "main" | "overlay" | "unknown"

export interface CompanionChatOwnershipResponse {
  conversation_id: string
  busy: boolean
  owner_id: string
  owner_surface: CompanionClientSurface
  request_id: number
  stale_after_seconds: number
}

export function getCompanionHandoff(): Promise<CompanionHandoffEnvelope> {
  return apiGet<CompanionHandoffEnvelope>("/api/companion/handoff")
}

export function createCompanionHandoff(
  payload: CompanionHandoffRequest,
): Promise<CompanionHandoff> {
  return apiPost<CompanionHandoff, CompanionHandoffRequest>(
    "/api/companion/handoff",
    payload,
  )
}

export function dismissCompanionHandoff(
  handoffId: string,
): Promise<CompanionHandoffEnvelope> {
  return apiPost<CompanionHandoffEnvelope, { handoff_id: string }>(
    "/api/companion/handoff/dismiss",
    { handoff_id: handoffId },
  )
}

export function getCompanionChatStatus(): Promise<CompanionChatStatusResponse> {
  return apiGet<CompanionChatStatusResponse>("/api/companion/chat/status")
}

export function getCompanionChatOwnership(
  conversationId: string,
): Promise<CompanionChatOwnershipResponse> {
  return apiGet<CompanionChatOwnershipResponse>(
    `/api/companion/chat/ownership/${encodeURIComponent(conversationId)}`,
  )
}

export function sendCompanionChat(
  payload: CompanionChatRequest,
): Promise<CompanionChatResponse> {
  return apiPost<CompanionChatResponse, CompanionChatRequest>(
    "/api/companion/chat",
    payload,
  )
}
