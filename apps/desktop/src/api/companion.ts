import { apiGet, apiPost } from "./client"
import type {
  CompanionChatRequest,
  CompanionChatResponse,
  CompanionChatStatusResponse,
  CompanionHandoff,
  CompanionHandoffEnvelope,
  CompanionHandoffRequest,
} from "./types"

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

export function sendCompanionChat(
  payload: CompanionChatRequest,
): Promise<CompanionChatResponse> {
  return apiPost<CompanionChatResponse, CompanionChatRequest>(
    "/api/companion/chat",
    payload,
  )
}
