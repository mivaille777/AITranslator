import { describe, expect, it } from "vitest"

import { buildCompanionChatRequest } from "./companion-runtime"

describe("companion ownership request contract", () => {
  it("includes the client identity and surface used by backend ownership", () => {
    const request = buildCompanionChatRequest({
      conversationId: "conversation-1",
      sessionId: "session-1",
      clientId: "overlay-client-1",
      clientSurface: "overlay",
      userMessage: "continue",
      contextMode: "general",
      messages: [],
      requestId: 12,
    })

    expect(request).toMatchObject({
      conversation_id: "conversation-1",
      client_id: "overlay-client-1",
      client_surface: "overlay",
      request_id: 12,
    })
  })
})
