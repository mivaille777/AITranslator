import { useEffect } from "react"
import { useMutation } from "@tanstack/react-query"
import ReactMarkdown from "react-markdown"

import { createCompanionHandoff } from "../api/companion"
import type {
  CompanionHandoffRequest,
  OverlayStateResponse,
  QuickActionResponse,
} from "../api/types"
import { desktop } from "../desktop"
import { readOverlayPreferences } from "../desktop/overlay-preferences"
import { useCompanionConversationRuntime } from "../features/companion/useCompanionConversationRuntime"
import {
  buildOverlayChatHandoff,
  contextFromOverlay,
} from "./overlay-chat-context"

export default function OverlayCompactChat({
  state,
  aiResult,
  onClose,
}: {
  state: OverlayStateResponse
  aiResult: QuickActionResponse | null
  onClose: () => void
}) {
  const context = contextFromOverlay(state, aiResult)
  const runtime = useCompanionConversationRuntime({
    initialContext: context,
    initialContextMode: "reading",
    initialSessionId: `overlay-${state.context_id}`,
    initialScopeId: `overlay:${state.context_id}`,
  })

  useEffect(() => {
    // Compact Chat is an explicit interactive mode. Temporarily override a
    // persistent click-through preference without changing the saved setting.
    document.documentElement.dataset.aitOverlayInteractive = "true"
    void desktop.overlay.setClickThrough(false)
    void desktop.overlay.focus()

    return () => {
      delete document.documentElement.dataset.aitOverlayInteractive
      void desktop.overlay.setClickThrough(readOverlayPreferences().clickThrough)
    }
  }, [])

  const handoffMutation = useMutation({
    mutationFn: (payload: CompanionHandoffRequest) => createCompanionHandoff(payload),
    onSuccess: async () => {
      await desktop.window.show()
      await desktop.window.focus()
    },
  })

  const recentMessages = runtime.messages.slice(-6)
  const latestAssistant = [...runtime.messages]
    .reverse()
    .find((message) => message.role === "assistant" && message.status === "complete")

  function exitChat() {
    runtime.closeActiveStream()
    onClose()
  }

  function openMainChat() {
    handoffMutation.mutate(
      buildOverlayChatHandoff(
        state,
        aiResult,
        latestAssistant?.content ?? "",
      ),
    )
  }

  return (
    <div className="border-b border-white/10 bg-black/10">
      <div className="flex items-center justify-between gap-3 px-3 py-2.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Back to translation"
              className="ait-overlay-quiet-button flex h-7 w-7 items-center justify-center rounded-full text-sm text-slate-300"
              onClick={exitChat}
            >
              ‹
            </button>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-slate-100">AI Chat</p>
              <p className="truncate text-[10px] text-slate-500">
                {runtime.contextMode === "reading"
                  ? state.resource_title || state.section_heading || "Current reading"
                  : "General conversation"}
              </p>
            </div>
          </div>
        </div>

        <button
          type="button"
          disabled={runtime.contextUpdating || runtime.activeRequestId !== null}
          className={`ait-overlay-quiet-button rounded-full px-2.5 py-1 text-[10px] font-medium ${
            runtime.contextMode === "reading" ? "text-cyan-200" : "text-slate-400"
          }`}
          onClick={() => void (
            runtime.contextMode === "reading"
              ? runtime.detachReadingContext()
              : runtime.attachSavedContext()
          )}
        >
          {runtime.contextMode === "reading" ? "Reading ●" : "General"}
        </button>
      </div>

      {aiResult && recentMessages.length === 0 && (
        <div className="mx-3 mb-2.5 rounded-[14px] border border-cyan-300/10 bg-cyan-300/[0.055] px-3 py-2.5">
          <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-cyan-200/60">
            Existing AI result
          </p>
          <p className="mt-1.5 line-clamp-3 text-[11px] leading-4 text-slate-300">
            {aiResult.output_text}
          </p>
        </div>
      )}

      <div className="h-[220px] overflow-y-auto px-3 py-2">
        {recentMessages.length === 0 ? (
          <div className="flex h-full items-center justify-center px-5 text-center">
            <div>
              <p className="text-xs font-medium text-slate-300">
                Ask about this selection
              </p>
              <p className="mt-1.5 text-[10px] leading-4 text-slate-500">
                The selected text, translation, and bounded nearby context are attached automatically.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-2.5">
            {recentMessages.map((message) => (
              <div
                key={message.id}
                className={message.role === "user"
                  ? "ml-auto max-w-[84%] rounded-[15px] bg-white/[0.11] px-3 py-2 text-[11px] leading-4 text-slate-100"
                  : "max-w-[92%] rounded-[15px] border border-white/[0.07] bg-white/[0.035] px-3 py-2 text-[11px] leading-4 text-slate-300"}
              >
                {message.role === "assistant" ? (
                  message.content ? (
                    <div className="max-w-none">
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>
                  ) : message.status === "streaming" ? (
                    <div className="flex items-center gap-2 text-slate-500">
                      <span className="h-3 w-3 animate-spin rounded-full border border-white/20 border-t-white/70" />
                      Thinking…
                    </div>
                  ) : (
                    <span className="text-slate-500">No response content.</span>
                  )
                ) : (
                  <p className="whitespace-pre-wrap">{message.content}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {runtime.errorMessage && (
        <p className="mx-3 mb-2 rounded-[12px] border border-rose-300/15 bg-rose-300/[0.08] px-3 py-2 text-[10px] leading-4 text-rose-200">
          {runtime.errorMessage}
        </p>
      )}

      {!runtime.chatAvailable && runtime.chatStatusLoaded && (
        <p className="mx-3 mb-2 rounded-[12px] border border-amber-300/15 bg-amber-300/[0.07] px-3 py-2 text-[10px] leading-4 text-amber-100/80">
          AI Chat unavailable · {runtime.chatStatusDetail}
        </p>
      )}

      <div className="border-t border-white/[0.07] px-3 py-2.5">
        <div className="flex items-end gap-2">
          <textarea
            autoFocus
            rows={1}
            value={runtime.draft}
            placeholder={runtime.activeRequestId === null ? "Ask a follow-up…" : "Generating…"}
            className="max-h-20 min-h-9 flex-1 resize-none rounded-[13px] border border-white/[0.08] bg-white/[0.055] px-3 py-2 text-[11px] leading-4 text-slate-100 outline-none placeholder:text-slate-600 focus:border-white/[0.16] focus:bg-white/[0.07]"
            onChange={(event) => runtime.setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault()
                event.stopPropagation()
                if (runtime.activeRequestId !== null) runtime.cancelStream()
                else exitChat()
                return
              }
              if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                event.preventDefault()
                openMainChat()
                return
              }
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault()
                runtime.sendMessage()
              }
            }}
          />
          {runtime.activeRequestId !== null ? (
            <button
              type="button"
              title="Stop generation"
              className="ait-overlay-action-button flex h-9 w-9 items-center justify-center rounded-full text-xs text-rose-200"
              onClick={runtime.cancelStream}
            >
              ■
            </button>
          ) : (
            <button
              type="button"
              title="Send · Enter"
              disabled={!runtime.chatAvailable || !runtime.draft.trim()}
              className="ait-overlay-action-button flex h-9 w-9 items-center justify-center rounded-full text-sm disabled:opacity-35"
              onClick={() => runtime.sendMessage()}
            >
              ↑
            </button>
          )}
        </div>

        <div className="mt-2 flex items-center justify-between gap-3">
          <span className="text-[9px] text-slate-600">
            Enter send · Shift+Enter newline · Esc back
          </span>
          <button
            type="button"
            disabled={handoffMutation.isPending}
            className="text-[9px] font-medium text-slate-500 hover:text-slate-300 disabled:opacity-40"
            onClick={openMainChat}
          >
            {handoffMutation.isPending ? "Opening…" : "Open main chat ↗"}
          </button>
        </div>
      </div>
    </div>
  )
}
