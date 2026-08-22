import type { DesktopPoint, OverlayPositionMode } from "./adapter"

export interface DesktopSize {
  width: number
  height: number
}

export interface DesktopRect extends DesktopPoint, DesktopSize {}

export interface OverlayPositionInput {
  mode: OverlayPositionMode
  cursor: DesktopPoint
  windowSize: DesktopSize
  workArea: DesktopRect
  customPosition?: DesktopPoint | null
  mouseOffset?: number
  positionMargin?: number
  edgePadding?: number
}

const DEFAULT_MOUSE_OFFSET = 16
const DEFAULT_POSITION_MARGIN = 24
const DEFAULT_EDGE_PADDING = 8

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum)
}

export function clampOverlayPosition(
  position: DesktopPoint,
  windowSize: DesktopSize,
  workArea: DesktopRect,
  edgePadding = DEFAULT_EDGE_PADDING,
): DesktopPoint {
  const minimumX = workArea.x + edgePadding
  const minimumY = workArea.y + edgePadding
  const maximumX = Math.max(
    minimumX,
    workArea.x + workArea.width - windowSize.width - edgePadding,
  )
  const maximumY = Math.max(
    minimumY,
    workArea.y + workArea.height - windowSize.height - edgePadding,
  )

  return {
    x: Math.round(clamp(position.x, minimumX, maximumX)),
    y: Math.round(clamp(position.y, minimumY, maximumY)),
  }
}

export function computeOverlayPosition(input: OverlayPositionInput): DesktopPoint {
  const mouseOffset = input.mouseOffset ?? DEFAULT_MOUSE_OFFSET
  const positionMargin = input.positionMargin ?? DEFAULT_POSITION_MARGIN
  const edgePadding = input.edgePadding ?? DEFAULT_EDGE_PADDING
  const { workArea, windowSize, cursor } = input

  let candidate: DesktopPoint

  switch (input.mode) {
    case "desktop_lyrics_bottom":
      candidate = {
        x: workArea.x + (workArea.width - windowSize.width) / 2,
        y: workArea.y + workArea.height - windowSize.height - positionMargin,
      }
      break
    case "desktop_lyrics_center":
      candidate = {
        x: workArea.x + (workArea.width - windowSize.width) / 2,
        y: workArea.y + (workArea.height - windowSize.height) / 2,
      }
      break
    case "desktop_lyrics_top":
      candidate = {
        x: workArea.x + (workArea.width - windowSize.width) / 2,
        y: workArea.y + positionMargin,
      }
      break
    case "custom_fixed_position":
      candidate = input.customPosition ?? {
        x: workArea.x + positionMargin,
        y: workArea.y + positionMargin,
      }
      break
    case "mouse_follow":
    default: {
      let x = cursor.x + mouseOffset
      let y = cursor.y + mouseOffset

      const rightLimit = workArea.x + workArea.width - edgePadding
      const bottomLimit = workArea.y + workArea.height - edgePadding

      if (x + windowSize.width > rightLimit) {
        x = cursor.x - windowSize.width - mouseOffset
      }
      if (y + windowSize.height > bottomLimit) {
        y = cursor.y - windowSize.height - mouseOffset
      }

      candidate = { x, y }
      break
    }
  }

  return clampOverlayPosition(candidate, windowSize, workArea, edgePadding)
}
