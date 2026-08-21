import { describe, expect, it } from "vitest"

import {
  overlayChatIsNearTail,
  overlayComposerHeight,
} from "./overlay-chat-behavior"

describe("overlay compact chat behavior", () => {
  it("follows the tail only while the reader remains near the latest message", () => {
    expect(overlayChatIsNearTail({ scrollTop: 360, clientHeight: 200, scrollHeight: 580 })).toBe(true)
    expect(overlayChatIsNearTail({ scrollTop: 120, clientHeight: 200, scrollHeight: 580 })).toBe(false)
  })

  it("clamps the composer to the compact-chat height budget", () => {
    expect(overlayComposerHeight(20)).toBe(36)
    expect(overlayComposerHeight(54)).toBe(54)
    expect(overlayComposerHeight(140)).toBe(80)
  })
})
