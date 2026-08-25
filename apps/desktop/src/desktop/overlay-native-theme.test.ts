/** @vitest-environment jsdom */

import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  invoke: vi.fn(),
  emitTo: vi.fn(),
  listen: vi.fn(),
}))

vi.mock("@tauri-apps/api/core", () => ({ invoke: mocks.invoke }))
vi.mock("@tauri-apps/api/event", () => ({ emitTo: mocks.emitTo, listen: mocks.listen }))

import {
  applyOverlayNativeVisualTheme,
  applyOverlayThemeToDocument,
  subscribeOverlayVisualThemeEvents,
} from "./overlay-native-theme"

describe("overlay native visual theme bridge", () => {
  beforeEach(() => {
    mocks.invoke.mockReset()
    mocks.emitTo.mockReset()
    mocks.listen.mockReset()
    mocks.invoke.mockResolvedValue(undefined)
    mocks.emitTo.mockResolvedValue(undefined)
    delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__
    delete document.documentElement.dataset.aitOverlayTheme
  })

  it("updates the overlay document theme without requiring Tauri", () => {
    applyOverlayThemeToDocument("light")
    expect(document.documentElement.dataset.aitOverlayTheme).toBe("light")
  })

  it("updates the native window and emits an explicit overlay event in Tauri", async () => {
    ;(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {}

    await applyOverlayNativeVisualTheme("dark")

    expect(mocks.invoke).toHaveBeenCalledWith("set_overlay_visual_theme", { theme: "dark" })
    expect(mocks.emitTo).toHaveBeenCalledWith(
      "overlay",
      "aitrans-overlay-visual-theme-changed",
      { theme: "dark" },
    )
  })

  it("accepts only supported themes from cross-window events", async () => {
    ;(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {}
    let handler: ((event: { payload?: { theme?: string } }) => void) | undefined
    mocks.listen.mockImplementation(async (_eventName, nextHandler) => {
      handler = nextHandler
      return () => undefined
    })
    const callback = vi.fn()

    await subscribeOverlayVisualThemeEvents(callback)
    handler?.({ payload: { theme: "light" } })
    handler?.({ payload: { theme: "unsupported" } })

    expect(callback).toHaveBeenCalledTimes(1)
    expect(callback).toHaveBeenCalledWith("light")
  })
})
