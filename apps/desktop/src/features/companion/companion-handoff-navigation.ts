import type { CompanionHandoff } from "../../api/types"

export function companionHandoffPath(handoff: CompanionHandoff | null): string {
  if (!handoff) return ""

  const conversationId = (handoff.conversation_id ?? "").trim()
  return conversationId
    ? `/chat?conversation=${encodeURIComponent(conversationId)}`
    : "/chat"
}
