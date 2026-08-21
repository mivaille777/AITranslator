import { describe, expect, it } from "vitest"

import { computeOverlayWindowSize } from "./overlay-sizing"

describe("computeOverlayWindowSize", () => {
  it("keeps loading compact", () => {
    expect(computeOverlayWindowSize({ phase: "loading" })).toEqual({
      width: 420,
      height: 190,
    })
  })

  it("expands error height only for longer messages", () => {
    const shortError = computeOverlayWindowSize({ phase: "error", message: "translation provider failed" })
    const longError = computeOverlayWindowSize({
      phase: "error",
      message: "The translation provider could not complete this request because the upstream service returned a temporary failure. Please retry in a moment.",
    })

    expect(shortError.height).toBeLessThan(longError.height)
    expect(shortError.height).toBeGreaterThanOrEqual(184)
    expect(longError.height).toBeLessThanOrEqual(272)
  })

  it("grows ready state with translated content and caps expanded results", () => {
    const shortReady = computeOverlayWindowSize({
      phase: "ready",
      translatedText: "Short translation.",
      sourceText: "Source text.",
    })
    const longResult = computeOverlayWindowSize({
      phase: "ready",
      translatedText: "Long translated content ".repeat(120),
      sourceText: "Long source content ".repeat(20),
      actionPresentation: "result",
    })

    expect(shortReady.height).toBeGreaterThanOrEqual(286)
    expect(longResult.height).toBeGreaterThan(shortReady.height)
    expect(longResult.height).toBe(600)
  })

  it("allocates more native height as contextual actions morph", () => {
    const base = {
      phase: "ready" as const,
      translatedText: "A compact result.",
      sourceText: "Source.",
    }
    const compact = computeOverlayWindowSize({ ...base, actionPresentation: "compact" })
    const expanded = computeOverlayWindowSize({ ...base, actionPresentation: "expanded" })
    const result = computeOverlayWindowSize({ ...base, actionPresentation: "result" })
    const chat = computeOverlayWindowSize({ ...base, actionPresentation: "chat" })

    expect(expanded.height).toBeGreaterThan(compact.height)
    expect(result.height).toBeGreaterThan(expanded.height)
    expect(chat.height).toBeGreaterThan(result.height)
    expect(chat.height).toBe(600)
  })

  it("keeps chat at a stable native cap independent of streaming text", () => {
    const shortChat = computeOverlayWindowSize({
      phase: "ready",
      translatedText: "Short.",
      sourceText: "Source.",
      actionPresentation: "chat",
    })
    const longChat = computeOverlayWindowSize({
      phase: "ready",
      translatedText: "Translation ".repeat(200),
      sourceText: "Source ".repeat(100),
      actionPresentation: "chat",
    })

    expect(shortChat.height).toBe(600)
    expect(longChat.height).toBe(600)
  })

  it("temporarily expands compact states while the context menu is open", () => {
    expect(computeOverlayWindowSize({ phase: "loading", menuOpen: true }).height).toBe(360)
  })
})