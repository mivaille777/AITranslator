export type CompanionRecoveryState = "idle" | "recovering" | "offline"

export function companionRecoveryLabel(
  state: CompanionRecoveryState,
  hasPersistedConversation: boolean,
): string {
  if (state === "recovering") {
    return hasPersistedConversation
      ? "Recovering persisted conversation…"
      : "Reconnecting to AI Chat…"
  }
  if (state === "offline") {
    return hasPersistedConversation
      ? "Conversation recovery needs attention."
      : "AI Chat connection is unavailable."
  }
  return ""
}
