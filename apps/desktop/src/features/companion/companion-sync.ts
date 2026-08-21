import type { CompanionConversationChangeSignal } from "../../desktop/adapter"

export type CompanionExternalChangeDecision =
  | "ignore"
  | "queue"
  | "refresh"
  | "delete"

export function companionExternalChangeDecision(
  signal: CompanionConversationChangeSignal,
  currentConversationId: string,
  busy: boolean,
): CompanionExternalChangeDecision {
  const changedConversationId = signal.conversationId.trim()
  const current = currentConversationId.trim()

  if (!changedConversationId || changedConversationId !== current) return "ignore"
  if (signal.kind === "deleted") return "delete"
  return busy ? "queue" : "refresh"
}
