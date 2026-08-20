import type { DesktopPoint, OverlayPositionMode } from "./adapter"

const STORAGE_KEY = "aitrans.overlay.preferences.v1"
const CHANGE_EVENT = "aitrans-overlay-preferences-changed"

export interface OverlayPreferences {
  positionMode: OverlayPositionMode
  alwaysOnTop: boolean
  locked: boolean
  clickThrough: boolean
  customPosition: DesktopPoint | null
}

export const DEFAULT_OVERLAY_PREFERENCES: OverlayPreferences = {
  positionMode: "mouse_follow",
  alwaysOnTop: true,
  locked: false,
  clickThrough: false,
  customPosition: null,
}

function isPositionMode(value: unknown): value is OverlayPositionMode {
  return [
    "mouse_follow",
    "desktop_lyrics_bottom",
    "desktop_lyrics_center",
    "desktop_lyrics_top",
    "custom_fixed_position",
  ].includes(String(value))
}

function isDesktopPoint(value: unknown): value is DesktopPoint {
  if (!value || typeof value !== "object") return false
  const candidate = value as Partial<DesktopPoint>
  return (
    typeof candidate.x === "number" &&
    Number.isFinite(candidate.x) &&
    typeof candidate.y === "number" &&
    Number.isFinite(candidate.y)
  )
}

export function readOverlayPreferences(): OverlayPreferences {
  if (typeof window === "undefined") return DEFAULT_OVERLAY_PREFERENCES

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_OVERLAY_PREFERENCES
    const parsed = JSON.parse(raw) as Partial<OverlayPreferences>

    return {
      positionMode: isPositionMode(parsed.positionMode)
        ? parsed.positionMode
        : DEFAULT_OVERLAY_PREFERENCES.positionMode,
      alwaysOnTop:
        typeof parsed.alwaysOnTop === "boolean"
          ? parsed.alwaysOnTop
          : DEFAULT_OVERLAY_PREFERENCES.alwaysOnTop,
      locked:
        typeof parsed.locked === "boolean"
          ? parsed.locked
          : DEFAULT_OVERLAY_PREFERENCES.locked,
      clickThrough:
        typeof parsed.clickThrough === "boolean"
          ? parsed.clickThrough
          : DEFAULT_OVERLAY_PREFERENCES.clickThrough,
      customPosition: isDesktopPoint(parsed.customPosition)
        ? parsed.customPosition
        : null,
    }
  } catch {
    return DEFAULT_OVERLAY_PREFERENCES
  }
}

export function writeOverlayPreferences(preferences: OverlayPreferences): OverlayPreferences {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: preferences }))
  }
  return preferences
}

export function updateOverlayPreferences(
  patch: Partial<OverlayPreferences>,
): OverlayPreferences {
  return writeOverlayPreferences({
    ...readOverlayPreferences(),
    ...patch,
  })
}

export function subscribeOverlayPreferences(
  callback: (preferences: OverlayPreferences) => void,
): () => void {
  if (typeof window === "undefined") return () => undefined

  const handleStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) callback(readOverlayPreferences())
  }
  const handleLocalChange = () => callback(readOverlayPreferences())

  window.addEventListener("storage", handleStorage)
  window.addEventListener(CHANGE_EVENT, handleLocalChange)
  return () => {
    window.removeEventListener("storage", handleStorage)
    window.removeEventListener(CHANGE_EVENT, handleLocalChange)
  }
}
