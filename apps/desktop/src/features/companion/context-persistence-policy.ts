import type { ChatContextMode, ConversationDetail } from "../../api/types"
import {
  companionContextSnapshot,
  type CompanionContextSnapshot,
} from "./companion-runtime"

export interface PersistedContextProjection {
  context: CompanionContextSnapshot
  contextMode: ChatContextMode
}

/**
 * Project a context PATCH response back into the live runtime without treating
 * it as a full conversation restore. In particular this helper never owns the
 * composer draft or message list.
 */
export function projectPersistedContext(
  conversation: ConversationDetail,
  preferredContext?: CompanionContextSnapshot,
): PersistedContextProjection {
  const persisted = companionContextSnapshot(conversation)
  return {
    context: preferredContext
      ? { ...persisted, ...preferredContext }
      : persisted,
    contextMode: conversation.context_mode,
  }
}
