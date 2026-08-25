import { invoke } from "@tauri-apps/api/core"
import { emitTo, listen } from "@tauri-apps/api/event"

import type { OverlayVisualTheme } from "./overlay-preferences"

const OVERLAY_VISUAL_THEME_CHANGED_EVENT = "aitrans-overlay-visual-theme-changed"

function hasTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window
}

export function applyOverlayThemeToDocument(theme: OverlayVisualTheme): void {
  if (typeof document === "undefined") return
  document.documentElement.dataset.aitOverlayTheme = theme
}

export async function applyOverlayNativeVisualTheme(
  theme: OverlayVisualTheme,
): Promise<void> {
  if (!hasTauriRuntime()) return

  await invoke("set_overlay_visual_theme", { theme })

  // localStorage remains the persisted source of truth, but a Tauri event makes
  // cross-window theme changes deterministic instead of relying on WebView2's
  // storage-event timing between the main window and the overlay document.
  await emitTo("overlay", OVERLAY_VISUAL_THEME_CHANGED_EVENT, { theme })
}

export async function subscribeOverlayVisualThemeEvents(
  callback: (theme: OverlayVisualTheme) => void,
): Promise<() => void> {
  if (!hasTauriRuntime()) return () => undefined

  return listen<{ theme?: string }>(OVERLAY_VISUAL_THEME_CHANGED_EVENT, (event) => {
    const theme = event.payload?.theme
    if (theme === "light" || theme === "dark") callback(theme)
  })
}
