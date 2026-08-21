import { apiDelete, apiGet, apiPatch, apiPost } from "./client"
import type {
  ConversationContextUpdate,
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

export function rewindConversation(
  conversationId: string,
  userMessageId: string,
): Promise<ConversationDetail> {
  return apiPost<ConversationDetail, { user_message_id: string }>(
    `/api/conversations/${encodeURIComponent(conversationId)}/rewind`,
    { user_message_id: userMessageId },
  )
}

export function updateConversationContext(
  conversationId: string,
  payload: ConversationContextUpdate,
): Promise<ConversationDetail> {
  return apiPatch<ConversationDetail, ConversationContextUpdate>(
    `/api/conversations/${encodeURIComponent(conversationId)}/context`,
    payload,
  )
}

export function deleteConversation(
  conversationId: string,
): Promise<ConversationDeleteResponse> {
  return apiDelete<ConversationDeleteResponse>(
    `/api/conversations/${encodeURIComponent(conversationId)}`,
  )
}
