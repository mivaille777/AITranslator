export interface OverlayWindowSize {
  width: number
  height: number
}

export type OverlayVisualPhase = "loading" | "ready" | "error"

export interface OverlaySizingInput {
  phase: OverlayVisualPhase
  translatedText?: string
  sourceText?: string
  message?: string
  menuOpen?: boolean
}

export const OVERLAY_WINDOW_WIDTH = 420

const MIN_HEIGHT = 184
const MENU_MIN_HEIGHT = 360
const READY_MIN_HEIGHT = 286
const READY_MAX_HEIGHT = 540

function wrappedLineCount(text: string, charsPerLine: number, maxLines: number): number {
  const normalized = text.trim()
  if (!normalized) return 0

  const lines = normalized.split(/\r?\n/).reduce((total, line) => {
    const length = Math.max(1, line.trim().length)
    return total + Math.max(1, Math.ceil(length / charsPerLine))
  }, 0)

  return Math.min(maxLines, lines)
}

export function computeOverlayWindowSize({
  phase,
  translatedText = "",
  sourceText = "",
  message = "",
  menuOpen = false,
}: OverlaySizingInput): OverlayWindowSize {
  let height: number

  if (phase === "loading") {
    height = 190
  } else if (phase === "error") {
    const messageLines = Math.max(1, wrappedLineCount(message, 42, 4))
    height = 184 + messageLines * 22
  } else {
    const translationLines = Math.max(1, wrappedLineCount(translatedText, 45, 11))
    const sourceLines = wrappedLineCount(sourceText, 54, 3)
    const translationHeight = translationLines * 24
    const sourceHeight = sourceLines > 0 ? 24 + sourceLines * 20 : 0
    const quickActionReserve = 70

    height = 154 + translationHeight + sourceHeight + quickActionReserve
    height = Math.max(READY_MIN_HEIGHT, Math.min(READY_MAX_HEIGHT, height))
  }

  if (menuOpen) height = Math.max(height, MENU_MIN_HEIGHT)

  return {
    width: OVERLAY_WINDOW_WIDTH,
    height: Math.max(MIN_HEIGHT, Math.round(height)),
  }
}
