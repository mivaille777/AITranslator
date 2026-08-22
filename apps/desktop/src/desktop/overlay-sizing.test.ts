import { describe, expect, it } from "vitest"

import { computeOverlayWindowSize } from "./overlay-sizing"

describe("computeOverlayWindowSize", () => {
  it("keeps hidden compact", () => {
    expect(computeOverlayWindowSize({ phase: "hidden" })).toEqual({
      width: 420,
      height: 190,
    })
  })

  it("uses a stable assistant height independent of cached translation text", () => {
    const plainAssistant = computeOverlayWindowSize({
      phase: "ready",
      mode: "assistant",
    })
    const assistantWithCachedTranslation = computeOverlayWindowSize({
      phase: "ready",
      mode: "assistant",
      translatedText: "Long translated content ".repeat(200),
      sourceText: "Long source content ".repeat(100),
    })

    expect(plainAssistant).toEqual({ width: 420, height: 430 })
    expect(assistantWithCachedTranslation).toEqual(plainAssistant)
  })

  it("reserves the full translation workspace while translation is active", () => {
    expect(computeOverlayWindowSize({
      phase: "ready",
      mode: "translation",
    })).toEqual({
      width: 420,
      height: 600,
    })
  })

  it("shrinks immediately when mode returns from translation to assistant", () => {
    const translation = computeOverlayWindowSize({ phase: "ready", mode: "translation" })
    const assistant = computeOverlayWindowSize({
      phase: "ready",
      mode: "assistant",
      translatedText: "cached translation remains available",
    })

    expect(translation.height).toBe(600)
    expect(assistant.height).toBe(430)
  })

  it("keeps translation loading and failures large enough for the persistent composer", () => {
    expect(computeOverlayWindowSize({
      phase: "loading",
      mode: "translation",
    }).height).toBe(560)
    expect(computeOverlayWindowSize({
      phase: "error",
      mode: "translation",
      message: "provider failed",
    }).height).toBe(560)
  })

  it("temporarily expands compact states while the context menu is open", () => {
    expect(computeOverlayWindowSize({ phase: "loading", menuOpen: true }).height).toBe(360)
  })
})
