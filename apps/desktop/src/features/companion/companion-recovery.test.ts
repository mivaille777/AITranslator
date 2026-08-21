import { describe, expect, it } from "vitest"

import { companionRecoveryLabel } from "./companion-recovery"

describe("companion recovery presentation", () => {
  it("distinguishes persisted recovery from first-send reconnects", () => {
    expect(companionRecoveryLabel("recovering", true)).toContain("persisted")
    expect(companionRecoveryLabel("recovering", false)).toContain("Reconnecting")
  })

  it("keeps idle state visually silent", () => {
    expect(companionRecoveryLabel("idle", true)).toBe("")
    expect(companionRecoveryLabel("idle", false)).toBe("")
  })
})
