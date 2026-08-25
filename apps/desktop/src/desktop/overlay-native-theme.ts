import { invoke } from "@tauri-apps/api/core"
import { emitTo, listen } from "@tauri-apps/api/event"
import { getCurrentWebview } from "@tauri-apps/api/webview"

import type { OverlayVisualTheme } from "./overlay-preferences"

const OVERLAY_VISUAL_THEME_CHANGED_EVENT = "aitrans-overlay-visual-theme-changed"

function hasTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window
}

export function applyOverlayThemeToDocument(theme: OverlayVisualTheme): void {
  if (typeof document === "undefined") return
  document.documentElement.dataset.aitOverlayTheme = theme
}

export async function applyOverlayWebviewMaterial(
  theme: OverlayVisualTheme,
): Promise<void> {
  if (!hasTauriRuntime()) return

  // WebView2 only honors fully transparent (alpha 0) or fully opaque colors on
  // Windows. Explicitly clear the overlay WebView for Liquid Glass so the DWM
  // system backdrop can be seen through the DOM. Restore the classic dark host
  // as an opaque surface when switching back to the legacy theme.
  await getCurrentWebview().setBackgroundColor(
    theme === "light" ? [0, 0, 0, 0] : [23, 23, 26, 255],
  )
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
