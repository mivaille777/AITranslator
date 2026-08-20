import type { DesktopAdapter } from "../adapter"

export const browserDesktopAdapter: DesktopAdapter = {
  runtime: "browser",
  window: {
    async show() {
      // Browser development mode has no native desktop window lifecycle.
    },
    async hide() {
      // Browser development mode has no native desktop window lifecycle.
    },
  },
}
