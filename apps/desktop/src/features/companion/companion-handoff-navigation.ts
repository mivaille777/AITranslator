import type { CompanionHandoff } from "../../api/types"

export function companionConversationPath(conversationId: string): string {
  const normalized = conversationId.trim()
  return normalized
    ? `/chat?conversation=${encodeURIComponent(normalized)}`
    : "/chat"
}

export function companionHandoffPath(handoff: CompanionHandoff | null): string {
  if (!handoff) return ""
  return companionConversationPath(handoff.conversation_id ?? "")
}
