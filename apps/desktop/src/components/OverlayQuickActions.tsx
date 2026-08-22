import { useCallback, useEffect } from "react"

import { switchOverlayMode } from "../api/overlay"
import type { OverlayStateResponse } from "../api/types"
import { subscribeOverlayCommands } from "../desktop/overlay-commands"
import type { OverlayActionPresentation } from "../desktop/overlay-sizing"
import OverlayCompactChat from "./OverlayCompactChat"

export type OverlayCompletedInteraction = "copy" | "handoff"

type OverlayQuickActionsProps = {
  state: OverlayStateResponse
  onPresentationChange?: (presentation: OverlayActionPresentation) => void
  onCompletedInteraction?: (interaction: OverlayCompletedInteraction) => void
}

export default function OverlayQuickActions({
  state,
  onPresentationChange,
}: OverlayQuickActionsProps) {
  const mode = state.mode ?? "assistant"

  const setPresentation = useCallback((presentation: OverlayActionPresentation) => {
    onPresentationChange?.(presentation)
  }, [onPresentationChange])

  const openAssistant = useCallback(() => {
    setPresentation("compact")
    if (mode === "assistant") return
    void switchOverlayMode(state.context_id, "assistant").catch(() => undefined)
  }, [mode, setPresentation, state.context_id])

  useEffect(() => {
    setPresentation(mode === "translation" ? "chat" : "compact")
  }, [mode, setPresentation])

  useEffect(() => subscribeOverlayCommands((command) => {
    if (command === "escape" && mode === "translation") {
      openAssistant()
    }
  }), [mode, openAssistant])

  if (!state.visible || state.phase === "hidden") return null

  return (
    <section
      className={`ait-overlay-action-surface relative ${mode === "assistant" ? "is-assistant-primary" : "is-translation-primary"}`}
      data-overlay-mode={mode}
    >
      <OverlayCompactChat
        state={state}
        aiResult={null}
        onClose={mode === "translation" ? openAssistant : () => undefined}
      />
    </section>
  )
}
