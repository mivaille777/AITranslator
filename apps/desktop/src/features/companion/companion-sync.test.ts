import { describe, expect, it } from "vitest"

import { companionExternalChangeDecision } from "./companion-sync"

describe("companionExternalChangeDecision", () => {
  it("ignores changes for another conversation", () => {
    expect(
      companionExternalChangeDecision(
        { conversationId: "conversation-b", kind: "updated" },
        "conversation-a",
        false,
      ),
    ).toBe("ignore")
  })

  it("refreshes the current conversation when idle", () => {
    expect(
      companionExternalChangeDecision(
        { conversationId: " conversation-a ", kind: "updated" },
        "conversation-a",
        false,
      ),
    ).toBe("refresh")
  })

  it("queues an external update while a local request is active", () => {
    expect(
      companionExternalChangeDecision(
        { conversationId: "conversation-a", kind: "updated" },
        "conversation-a",
        true,
      ),
    ).toBe("queue")
  })

  it("applies deletion immediately even while busy", () => {
    expect(
      companionExternalChangeDecision(
        { conversationId: "conversation-a", kind: "deleted" },
        "conversation-a",
        true,
      ),
    ).toBe("delete")
  })
})
