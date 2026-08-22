export interface OverlayWindowSize {
  width: number
  height: number
}

export type OverlayVisualPhase = "hidden" | "idle" | "loading" | "ready" | "error"
export type OverlayActionPresentation = "compact" | "expanded" | "result" | "chat"

export interface OverlaySizingInput {
  phase: OverlayVisualPhase
  translatedText?: string
  sourceText?: string
  message?: string
  menuOpen?: boolean
  actionPresentation?: OverlayActionPresentation
}

export const OVERLAY_WINDOW_WIDTH = 420

const MIN_HEIGHT = 184
const MENU_MIN_HEIGHT = 360
const READY_MIN_HEIGHT = 286
const READY_MAX_HEIGHT = 600

const ACTION_RESERVE: Record<OverlayActionPresentation, number> = {
  compact: 154,
  expanded: 194,
  result: 224,
  // Interactive Translation now owns an editable source, language/provider
  // controls, translated output and the persistent companion composer.
  chat: 430,
}

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
  actionPresentation = "compact",
}: OverlaySizingInput): OverlayWindowSize {
  let height: number

  if (phase === "hidden") {
    height = 190
  } else if (phase === "idle") {
    height = READY_MIN_HEIGHT
  } else if (phase === "loading") {
    height = actionPresentation === "chat" ? 560 : 230
  } else if (phase === "error") {
    const messageLines = Math.max(1, wrappedLineCount(message, 42, 4))
    const errorHeight = 184 + messageLines * 22
    height = actionPresentation === "chat" ? Math.max(560, errorHeight) : errorHeight
  } else {
    const translationLines = Math.max(1, wrappedLineCount(translatedText, 45, 11))
    const sourceLines = wrappedLineCount(sourceText, 54, 3)
    const translationHeight = translationLines * 24
    const sourceHeight = sourceLines > 0 ? 24 + sourceLines * 20 : 0

    height = 148 + translationHeight + sourceHeight + ACTION_RESERVE[actionPresentation]
    height = Math.max(READY_MIN_HEIGHT, Math.min(READY_MAX_HEIGHT, height))
  }

  if (menuOpen) height = Math.max(height, MENU_MIN_HEIGHT)

  return {
    width: OVERLAY_WINDOW_WIDTH,
    height: Math.max(MIN_HEIGHT, Math.round(height)),
  }
}
