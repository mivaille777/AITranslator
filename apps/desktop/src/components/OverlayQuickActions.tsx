import { useCallback, useEffect } from "react"

import { switchOverlayMode } from "../api/overlay"
import type { OverlayStateResponse } from "../api/types"
import { subscribeOverlayCommands } from "../desktop/overlay-commands"
import OverlayCompactChat from "./OverlayCompactChat"
import OverlaySourceContext from "./OverlaySourceContext"
import OverlayTranslationWorkspace from "./OverlayTranslationWorkspace"

type OverlayQuickActionsProps = {
  state: OverlayStateResponse
}

export default function OverlayQuickActions({ state }: OverlayQuickActionsProps) {
  const mode = state.mode ?? "assistant"

  const openAssistant = useCallback(() => {
    if (mode === "assistant") return
    void switchOverlayMode(state.context_id, "assistant").catch(() => undefined)
  }, [mode, state.context_id])

  useEffect(() => subscribeOverlayCommands((command) => {
    if (command === "escape" && mode === "translation") {
      openAssistant()
    }
  }), [mode, openAssistant])

  if (!state.visible || state.phase === "hidden") return null

  return (
    <section
      className="ait-overlay-layout relative flex min-h-0 flex-1 flex-col overflow-hidden"
      data-overlay-mode={mode}
    >
      <OverlaySourceContext state={state} />
      <OverlayTranslationWorkspace state={state} visible={mode === "translation"} />
      <OverlayCompactChat
        state={state}
        aiResult={null}
        onClose={mode === "translation" ? openAssistant : () => undefined}
      />
    </section>
  )
}
