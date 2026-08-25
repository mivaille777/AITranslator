/** @vitest-environment jsdom */

import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  invoke: vi.fn(),
  emitTo: vi.fn(),
  listen: vi.fn(),
  startDragging: vi.fn(),
  getCurrentWindow: vi.fn(),
}))

vi.mock("@tauri-apps/api/core", () => ({ invoke: mocks.invoke }))
vi.mock("@tauri-apps/api/event", () => ({ emitTo: mocks.emitTo, listen: mocks.listen }))
vi.mock("@tauri-apps/api/window", () => ({ getCurrentWindow: mocks.getCurrentWindow }))

import {
  applyOverlayNativeVisualTheme,
  applyOverlayThemeToDocument,
  startOverlayWindowDrag,
  subscribeOverlayVisualThemeEvents,
} from "./overlay-native-theme"

describe("overlay native visual theme bridge", () => {
  beforeEach(() => {
    mocks.invoke.mockReset()
    mocks.emitTo.mockReset()
    mocks.listen.mockReset()
    mocks.startDragging.mockReset()
    mocks.getCurrentWindow.mockReset()
    mocks.invoke.mockResolvedValue(undefined)
    mocks.emitTo.mockResolvedValue(undefined)
    mocks.startDragging.mockResolvedValue(undefined)
    mocks.getCurrentWindow.mockReturnValue({ startDragging: mocks.startDragging })
    delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__
    delete document.documentElement.dataset.aitOverlayTheme
  })

  it("updates the overlay document theme without requiring Tauri", () => {
    applyOverlayThemeToDocument("light")
    expect(document.documentElement.dataset.aitOverlayTheme).toBe("light")
  })

  it("uses the no-backdrop native branch while preserving the light DOM theme event", async () => {
    ;(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {}

    await applyOverlayNativeVisualTheme("light")

    expect(mocks.invoke).toHaveBeenCalledWith("set_overlay_visual_theme", { theme: "dark" })
    expect(mocks.emitTo).toHaveBeenCalledWith(
      "overlay",
      "aitrans-overlay-visual-theme-changed",
      { theme: "light" },
    )
  })

  it("keeps the dark theme on the no-backdrop native branch", async () => {
    ;(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {}

    await applyOverlayNativeVisualTheme("dark")

    expect(mocks.invoke).toHaveBeenCalledWith("set_overlay_visual_theme", { theme: "dark" })
    expect(mocks.emitTo).toHaveBeenCalledWith(
      "overlay",
      "aitrans-overlay-visual-theme-changed",
      { theme: "dark" },
    )
  })

  it("starts native dragging explicitly instead of depending on a deep drag region", async () => {
    ;(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {}

    await startOverlayWindowDrag()

    expect(mocks.getCurrentWindow).toHaveBeenCalledTimes(1)
    expect(mocks.startDragging).toHaveBeenCalledTimes(1)
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
