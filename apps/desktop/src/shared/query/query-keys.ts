export const queryKeys = {
  health: ["health"] as const,
  translation: {
    status: ["translation", "status"] as const,
  },
  browser: {
    status: ["browser", "status"] as const,
    selection: ["browser", "selection"] as const,
    page: ["browser", "page"] as const,
  },
  overlay: {
    state: ["overlay", "state"] as const,
  },
  quickActions: {
    status: ["quick-actions", "status"] as const,
  },
  companion: {
    handoff: ["companion", "handoff"] as const,
    chatStatus: ["companion", "chat-status"] as const,
  },
  conversations: {
    list: (limit: number) => ["conversations", "list", limit] as const,
    detail: (conversationId: string) => ["conversations", "detail", conversationId] as const,
  },
  research: {
    notes: (limit: number) => ["research", "notes", limit] as const,
  },
} as const

export const queryPolling = {
  health: 5_000,
  translationStatus: 15_000,
  browserStatus: 2_000,
  browserSelection: 500,
  browserPage: 2_000,
  overlayState: 250,
  companionHandoff: 650,
  companionChatStatus: 30_000,
  conversationList: 5_000,
  researchNotes: 5_000,
} as const
