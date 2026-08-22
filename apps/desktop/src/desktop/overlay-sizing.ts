export interface OverlayWindowSize {
  width: number
  height: number
}

export type OverlayVisualPhase = "hidden" | "idle" | "loading" | "ready" | "error"
export type OverlayActionPresentation = "compact" | "expanded" | "result" | "chat"
export type OverlaySizingMode = "assistant" | "translation"

export interface OverlaySizingInput {
  phase: OverlayVisualPhase
  mode?: OverlaySizingMode
  translatedText?: string
  sourceText?: string
  message?: string
  menuOpen?: boolean
  actionPresentation?: OverlayActionPresentation
}

export const OVERLAY_WINDOW_WIDTH = 420

const MIN_HEIGHT = 184
const MENU_MIN_HEIGHT = 360
const ASSISTANT_IDLE_HEIGHT = 360
const ASSISTANT_READY_HEIGHT = 430
const ASSISTANT_ERROR_HEIGHT = 400
const TRANSLATION_HEIGHT = 600
const TRANSLATION_TRANSIENT_HEIGHT = 560

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
  mode = "assistant",
  message = "",
  menuOpen = false,
}: OverlaySizingInput): OverlayWindowSize {
  let height: number

  if (phase === "hidden") {
    height = 190
  } else if (mode === "translation") {
    height = phase === "ready" ? TRANSLATION_HEIGHT : TRANSLATION_TRANSIENT_HEIGHT
  } else if (phase === "idle") {
    height = ASSISTANT_IDLE_HEIGHT
  } else if (phase === "loading") {
    height = ASSISTANT_IDLE_HEIGHT
  } else if (phase === "error") {
    const messageLines = Math.max(1, wrappedLineCount(message, 42, 4))
    height = Math.max(ASSISTANT_ERROR_HEIGHT, 300 + messageLines * 20)
  } else {
    // Conversation content owns its own scroll viewport. Cached translation
    // text must never keep the Assistant native window at Translation height.
    height = ASSISTANT_READY_HEIGHT
  }

  if (menuOpen) height = Math.max(height, MENU_MIN_HEIGHT)

  return {
    width: OVERLAY_WINDOW_WIDTH,
    height: Math.max(MIN_HEIGHT, Math.round(height)),
  }
}
