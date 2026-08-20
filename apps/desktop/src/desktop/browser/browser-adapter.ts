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
    async focus() {
      window.focus()
    },
  },
  overlay: {
    async show() {
      // Browser development mode has no native overlay window.
    },
    async hide() {
      // Browser development mode has no native overlay window.
    },
    async focus() {
      window.focus()
    },
    async place() {
      return null
    },
    async startDragging() {
      // Browser development mode cannot start a native window drag.
    },
    async getPosition() {
      return null
    },
    async setAlwaysOnTop() {
      // No-op outside a desktop runtime.
    },
    async setClickThrough() {
      // No-op outside a desktop runtime.
    },
    async onMoved() {
      return () => undefined
    },
  },
}
