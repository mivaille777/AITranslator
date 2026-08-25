/** @vitest-environment jsdom */

import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  invoke: vi.fn(),
  emitTo: vi.fn(),
  listen: vi.fn(),
  startDragging: vi.fn(),
  setDecorations: vi.fn(),
  setResizable: vi.fn(),
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
    mocks.setDecorations.mockReset()
    mocks.setResizable.mockReset()
    mocks.getCurrentWindow.mockReset()
    mocks.invoke.mockResolvedValue(undefined)
    mocks.emitTo.mockResolvedValue(undefined)
    mocks.startDragging.mockResolvedValue(undefined)
    mocks.setDecorations.mockResolvedValue(undefined)
    mocks.setResizable.mockResolvedValue(undefined)
    mocks.getCurrentWindow.mockReturnValue({
      startDragging: mocks.startDragging,
      setDecorations: mocks.setDecorations,
      setResizable: mocks.setResizable,
    })
    delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__
    delete document.documentElement.dataset.aitOverlayTheme
  })

  it("updates the overlay document theme without requiring Tauri", () => {
    applyOverlayThemeToDocument("light")
    expect(document.documentElement.dataset.aitOverlayTheme).toBe("light")
  })

  it("reasserts borderless chrome around native light-theme updates", async () => {
    ;(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {}

    await applyOverlayNativeVisualTheme("light")

    expect(mocks.setResizable).toHaveBeenCalledTimes(2)
    expect(mocks.setResizable).toHaveBeenNthCalledWith(1, false)
    expect(mocks.setDecorations).toHaveBeenCalledTimes(2)
    expect(mocks.setDecorations).toHaveBeenNthCalledWith(1, false)
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

  it("starts native dragging only after removing decorations", async () => {
    ;(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {}

    await startOverlayWindowDrag()

    expect(mocks.getCurrentWindow).toHaveBeenCalledTimes(1)
    expect(mocks.setResizable).toHaveBeenCalledWith(false)
    expect(mocks.setDecorations).toHaveBeenCalledWith(false)
    expect(mocks.startDragging).toHaveBeenCalledTimes(1)
    expect(mocks.setDecorations.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.startDragging.mock.invocationCallOrder[0],
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
