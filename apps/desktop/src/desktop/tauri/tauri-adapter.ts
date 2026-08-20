import { getCurrentWindow } from "@tauri-apps/api/window"

import type { DesktopAdapter } from "../adapter"

export const tauriDesktopAdapter: DesktopAdapter = {
  runtime: "tauri",
  window: {
    async show() {
      await getCurrentWindow().show()
    },
    async hide() {
      await getCurrentWindow().hide()
    },
  },
}
