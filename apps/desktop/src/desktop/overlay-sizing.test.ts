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

    expect(expanded.height).toBeGreaterThan(compact.height)
    expect(result.height).toBeGreaterThan(expanded.height)
  })

  it("temporarily expands compact states while the context menu is open", () => {
    expect(computeOverlayWindowSize({ phase: "loading", menuOpen: true }).height).toBe(360)
  })
})
