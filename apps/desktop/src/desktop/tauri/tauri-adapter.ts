import {
  PhysicalPosition,
  Window as TauriWindow,
  cursorPosition,
  getCurrentWindow,
  monitorFromPoint,
  primaryMonitor,
} from "@tauri-apps/api/window"

import type {
  DesktopAdapter,
  DesktopPoint,
  OverlayPositionMode,
} from "../adapter"
import { computeOverlayPosition } from "../overlay-positioning"

async function getMainWindow(): Promise<TauriWindow | null> {
  const current = getCurrentWindow()
  if (current.label === "main") return current
  return TauriWindow.getByLabel("main")
}

async function getOverlayWindow(): Promise<TauriWindow | null> {
  const current = getCurrentWindow()
  if (current.label === "overlay") return current
  return TauriWindow.getByLabel("overlay")
}

async function placeOverlay(
  mode: OverlayPositionMode,
  customPosition?: DesktopPoint | null,
): Promise<DesktopPoint | null> {
  const overlay = await getOverlayWindow()
  if (!overlay) return null

  const cursor = await cursorPosition()
  const reference =
    mode === "custom_fixed_position" && customPosition
      ? customPosition
      : { x: cursor.x, y: cursor.y }

  const monitor =
    (await monitorFromPoint(reference.x, reference.y)) ??
    (await monitorFromPoint(cursor.x, cursor.y)) ??
    (await primaryMonitor())
  if (!monitor) return null

  const size = await overlay.outerSize()
  const workArea = monitor.workArea
  const position = computeOverlayPosition({
    mode,
    cursor: { x: cursor.x, y: cursor.y },
    windowSize: { width: size.width, height: size.height },
    workArea: {
      x: workArea.position.x,
      y: workArea.position.y,
      width: workArea.size.width,
      height: workArea.size.height,
    },
    customPosition,
  })

  await overlay.setPosition(new PhysicalPosition(position.x, position.y))
  return position
}

export const tauriDesktopAdapter: DesktopAdapter = {
  runtime: "tauri",
  window: {
    async show() {
      const main = await getMainWindow()
      await main?.show()
    },
    async hide() {
      const main = await getMainWindow()
      await main?.hide()
    },
    async focus() {
      const main = await getMainWindow()
      await main?.show()
      await main?.setFocus()
    },
  },
  overlay: {
    async show() {
      const overlay = await getOverlayWindow()
      await overlay?.show()
    },
    async hide() {
      const overlay = await getOverlayWindow()
      await overlay?.hide()
    },
    async focus() {
      const overlay = await getOverlayWindow()
      await overlay?.setFocus()
    },
    place: placeOverlay,
    async startDragging() {
      const overlay = await getOverlayWindow()
      await overlay?.startDragging()
    },
    async getPosition() {
      const overlay = await getOverlayWindow()
      if (!overlay) return null
      const position = await overlay.outerPosition()
      return { x: position.x, y: position.y }
    },
    async setAlwaysOnTop(enabled: boolean) {
      const overlay = await getOverlayWindow()
      await overlay?.setAlwaysOnTop(enabled)
    },
    async setClickThrough(enabled: boolean) {
      const overlay = await getOverlayWindow()
      await overlay?.setIgnoreCursorEvents(enabled)
    },
    async onMoved(callback) {
      const overlay = await getOverlayWindow()
      if (!overlay) return () => undefined
      return overlay.onMoved(({ payload }) => {
        callback({ x: payload.x, y: payload.y })
      })
    },
  },
}
