import {
  LogicalSize,
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
  DesktopSize,
  OverlayPositionMode,
} from "../adapter"
import { computeOverlayPosition } from "../overlay-positioning"

let overlayResizeGeneration = 0

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

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(value, Math.max(minimum, maximum)))
}

async function keepOverlayInsideWorkArea(overlay: TauriWindow): Promise<void> {
  const position = await overlay.outerPosition()
  const size = await overlay.outerSize()
  const monitor =
    (await monitorFromPoint(position.x, position.y)) ??
    (await primaryMonitor())
  if (!monitor) return

  const workArea = monitor.workArea
  const minX = workArea.position.x
  const minY = workArea.position.y
  const maxX = minX + workArea.size.width - size.width
  const maxY = minY + workArea.size.height - size.height
  const nextX = clamp(position.x, minX, maxX)
  const nextY = clamp(position.y, minY, maxY)

  if (nextX !== position.x || nextY !== position.y) {
    await overlay.setPosition(new PhysicalPosition(nextX, nextY))
  }
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

async function resizeOverlay(target: DesktopSize): Promise<void> {
  const overlay = await getOverlayWindow()
  if (!overlay) return

  const generation = ++overlayResizeGeneration
  const scaleFactor = await overlay.scaleFactor()
  const current = await overlay.outerSize()
  const startWidth = current.width / scaleFactor
  const startHeight = current.height / scaleFactor
  const deltaWidth = target.width - startWidth
  const deltaHeight = target.height - startHeight

  if (Math.abs(deltaWidth) < 1 && Math.abs(deltaHeight) < 1) {
    await keepOverlayInsideWorkArea(overlay)
    return
  }

  const steps = 8
  const stepDelay = 18
  for (let step = 1; step <= steps; step += 1) {
    if (generation !== overlayResizeGeneration) return

    const t = step / steps
    const eased = 1 - Math.pow(1 - t, 4)
    await overlay.setSize(
      new LogicalSize(
        Math.round(startWidth + deltaWidth * eased),
        Math.round(startHeight + deltaHeight * eased),
      ),
    )

    if (step < steps) {
      await new Promise<void>((resolve) => window.setTimeout(resolve, stepDelay))
    }
  }

  if (generation === overlayResizeGeneration) {
    await keepOverlayInsideWorkArea(overlay)
  }
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
      overlayResizeGeneration += 1
      const overlay = await getOverlayWindow()
      await overlay?.hide()
    },
    async focus() {
      const overlay = await getOverlayWindow()
      await overlay?.setFocus()
    },
    place: placeOverlay,
    resize: resizeOverlay,
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
