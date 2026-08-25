/** @vitest-environment jsdom */

import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  invoke: vi.fn(),
  emitTo: vi.fn(),
  listen: vi.fn(),
  setBackgroundColor: vi.fn(),
  getCurrentWebview: vi.fn(),
}))

vi.mock("@tauri-apps/api/core", () => ({ invoke: mocks.invoke }))
vi.mock("@tauri-apps/api/event", () => ({ emitTo: mocks.emitTo, listen: mocks.listen }))
vi.mock("@tauri-apps/api/webview", () => ({ getCurrentWebview: mocks.getCurrentWebview }))

import {
  applyOverlayNativeVisualTheme,
  applyOverlayThemeToDocument,
  applyOverlayWebviewMaterial,
  subscribeOverlayVisualThemeEvents,
} from "./overlay-native-theme"

describe("overlay native visual theme bridge", () => {
  beforeEach(() => {
    mocks.invoke.mockReset()
    mocks.emitTo.mockReset()
    mocks.listen.mockReset()
    mocks.setBackgroundColor.mockReset()
    mocks.getCurrentWebview.mockReset()
    mocks.invoke.mockResolvedValue(undefined)
    mocks.emitTo.mockResolvedValue(undefined)
    mocks.setBackgroundColor.mockResolvedValue(undefined)
    mocks.getCurrentWebview.mockReturnValue({ setBackgroundColor: mocks.setBackgroundColor })
    delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__
    delete document.documentElement.dataset.aitOverlayTheme
  })

  it("updates the overlay document theme without requiring Tauri", () => {
    applyOverlayThemeToDocument("light")
    expect(document.documentElement.dataset.aitOverlayTheme).toBe("light")
  })

  it("makes the overlay WebView fully transparent for Liquid Glass", async () => {
    ;(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {}

    await applyOverlayWebviewMaterial("light")

    expect(mocks.getCurrentWebview).toHaveBeenCalledTimes(1)
    expect(mocks.setBackgroundColor).toHaveBeenCalledWith([0, 0, 0, 0])
  })

  it("restores an opaque WebView background for the classic dark theme", async () => {
    ;(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {}

    await applyOverlayWebviewMaterial("dark")

    expect(mocks.setBackgroundColor).toHaveBeenCalledWith([23, 23, 26, 255])
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
