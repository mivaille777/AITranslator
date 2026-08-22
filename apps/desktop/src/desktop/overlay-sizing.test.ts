import { describe, expect, it } from "vitest"

import { computeOverlayWindowSize } from "./overlay-sizing"

describe("computeOverlayWindowSize", () => {
  it("keeps hidden compact", () => {
    expect(computeOverlayWindowSize({ phase: "hidden" })).toEqual({
      width: 420,
      height: 190,
    })
  })

  it("keeps the companion composer visible while translation is loading", () => {
    const compactLoading = computeOverlayWindowSize({ phase: "loading" })
    const translationLoading = computeOverlayWindowSize({
      phase: "loading",
      actionPresentation: "chat",
    })

    expect(compactLoading.height).toBe(230)
    expect(translationLoading.height).toBe(520)
  })

  it("expands error height and keeps chat available in translation errors", () => {
    const shortError = computeOverlayWindowSize({ phase: "error", message: "translation provider failed" })
    const chatError = computeOverlayWindowSize({
      phase: "error",
      message: "translation provider failed",
      actionPresentation: "chat",
    })

    expect(shortError.height).toBeGreaterThanOrEqual(184)
    expect(chatError.height).toBeGreaterThanOrEqual(520)
  })

  it("reserves enough compact height for assistant composer-first layout", () => {
    const assistant = computeOverlayWindowSize({
      phase: "ready",
      sourceText: "A selected paragraph that should appear in the AI composer.",
      actionPresentation: "compact",
    })

    expect(assistant.height).toBeGreaterThanOrEqual(370)
    expect(assistant.height).toBeLessThan(520)
  })

  it("grows ready state with translated content and caps long translation chat", () => {
    const shortTranslation = computeOverlayWindowSize({
      phase: "ready",
      translatedText: "Short translation.",
      sourceText: "Source text.",
      actionPresentation: "chat",
    })
    const longTranslation = computeOverlayWindowSize({
      phase: "ready",
      translatedText: "Long translated content ".repeat(120),
      sourceText: "Long source content ".repeat(20),
      actionPresentation: "chat",
    })

    expect(shortTranslation.height).toBeGreaterThanOrEqual(500)
    expect(longTranslation.height).toBe(600)
  })

  it("temporarily expands compact states while the context menu is open", () => {
    expect(computeOverlayWindowSize({ phase: "loading", menuOpen: true }).height).toBe(360)
  })
})
