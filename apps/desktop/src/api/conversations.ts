import { apiDelete, apiGet, apiPatch } from "./client"
import type {
  ConversationDeleteResponse,
  ConversationDetail,
  ConversationListResponse,
} from "./types"

export function getConversations(limit = 30): Promise<ConversationListResponse> {
  return apiGet<ConversationListResponse>(`/api/conversations?limit=${limit}`)
}

export function getConversation(conversationId: string): Promise<ConversationDetail> {
  return apiGet<ConversationDetail>(`/api/conversations/${encodeURIComponent(conversationId)}`)
}

export function renameConversation(
  conversationId: string,
  title: string,
): Promise<ConversationDetail> {
  return apiPatch<ConversationDetail, { title: string }>(
    `/api/conversations/${encodeURIComponent(conversationId)}`,
    { title },
  )
}

export function deleteConversation(
  conversationId: string,
): Promise<ConversationDeleteResponse> {
  return apiDelete<ConversationDeleteResponse>(
    `/api/conversations/${encodeURIComponent(conversationId)}`,
  )
}
