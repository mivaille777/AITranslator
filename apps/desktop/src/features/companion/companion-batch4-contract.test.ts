import { describe, expect, it } from "vitest"

import { overlayChatIsNearTail, overlayComposerHeight } from "../../components/overlay-chat-behavior"
import { buildCompanionChatRequest } from "./companion-runtime"
import { companionRecoveryLabel } from "./companion-recovery"
import { companionExternalChangeDecision } from "./companion-sync"

describe("Batch 4 companion cross-window contract", () => {
  it("keeps main and overlay on the same conversation while preserving execution identity", () => {
    const main = buildCompanionChatRequest({
      conversationId: "conversation-shared",
      sessionId: "session-shared",
      clientId: "main-client",
      clientSurface: "main",
      userMessage: "continue in main",
      contextMode: "general",
      messages: [],
      requestId: 4,
    })
    const overlay = buildCompanionChatRequest({
      conversationId: "conversation-shared",
      sessionId: "session-shared",
      clientId: "overlay-client",
      clientSurface: "overlay",
      userMessage: "continue in overlay",
      contextMode: "general",
      messages: [],
      requestId: 5,
    })

    expect(main.conversation_id).toBe(overlay.conversation_id)
    expect(main.client_surface).toBe("main")
    expect(overlay.client_surface).toBe("overlay")
    expect(main.client_id).not.toBe(overlay.client_id)
  })

  it("queues peer updates during local generation and applies peer deletion immediately", () => {
    expect(
      companionExternalChangeDecision(
        { conversationId: "conversation-shared", kind: "updated" },
        "conversation-shared",
        true,
      ),
    ).toBe("queue")
    expect(
      companionExternalChangeDecision(
        { conversationId: "conversation-shared", kind: "deleted" },
        "conversation-shared",
        true,
      ),
    ).toBe("delete")
  })

  it("keeps compact UX bounded while recovery remains explicit", () => {
    expect(overlayComposerHeight(200)).toBe(80)
    expect(
      overlayChatIsNearTail({ scrollTop: 20, clientHeight: 200, scrollHeight: 600 }),
    ).toBe(false)
    expect(companionRecoveryLabel("recovering", true)).toContain("persisted")
    expect(companionRecoveryLabel("offline", false)).toContain("unavailable")
  })
})
