import { invoke } from "@tauri-apps/api/core"

import type { OverlayVisualTheme } from "./overlay-preferences"

export function applyOverlayThemeToDocument(theme: OverlayVisualTheme): void {
  if (typeof document === "undefined") return
  document.documentElement.dataset.aitOverlayTheme = theme
}

export async function applyOverlayNativeVisualTheme(
  theme: OverlayVisualTheme,
): Promise<void> {
  if (typeof window === "undefined" || !("__TAURI_INTERNALS__" in window)) return
  await invoke("set_overlay_visual_theme", { theme })
}
