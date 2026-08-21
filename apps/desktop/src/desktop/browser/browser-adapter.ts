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
    async resize() {
      // Browser development mode cannot resize a native overlay window.
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
    async notifyStateChanged() {
      // Polling remains the browser-development fallback.
    },
    async onStateChanged() {
      return () => undefined
    },
  },
}
