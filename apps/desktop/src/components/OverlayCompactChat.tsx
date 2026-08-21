import { useEffect, useRef, useState } from "react"
import { useMutation } from "@tanstack/react-query"
import ReactMarkdown from "react-markdown"

import { createCompanionHandoff } from "../api/companion"
import { bindOverlayCompanionConversation } from "../api/overlay"
import type {
  CompanionHandoffRequest,
  OverlayStateResponse,
  QuickActionResponse,
} from "../api/types"
import { desktop } from "../desktop"
import { readOverlayPreferences } from "../desktop/overlay-preferences"
import { previousCompanionUserMessage } from "../features/companion/companion-runtime"
import { useCompanionConversationRuntime } from "../features/companion/useCompanionConversationRuntime"
import {
  overlayChatIsNearTail,
  overlayComposerHeight,
} from "./overlay-chat-behavior"
import {
  buildOverlayChatHandoff,
  contextFromOverlay,
  overlayCompanionConversationId,
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
  const messageScrollRef = useRef<HTMLDivElement | null>(null)
  const composerRef = useRef<HTMLTextAreaElement | null>(null)
  const followTailRef = useRef(true)
  const [showJumpToLatest, setShowJumpToLatest] = useState(false)
  const context = contextFromOverlay(state, aiResult)
  const persistedConversationId = overlayCompanionConversationId(state)
  const runtime = useCompanionConversationRuntime({
    initialContext: context,
    initialContextMode: "reading",
    initialSessionId: `overlay-${state.context_id}`,
    initialScopeId: `overlay:${state.context_id}`,
    clientSurface: "overlay",
    onConversationAccepted: (conversationId) => {
      void bindOverlayCompanionConversation(state.context_id, conversationId).catch(() => {
        // The context may have changed while the first response was accepted.
        // A stale binding must never overwrite the newer selection.
      })
    },
  })
  const runtimeConversationId = runtime.conversationId
  const openRuntimeConversation = runtime.openConversation

  useEffect(() => {
    if (!persistedConversationId || runtimeConversationId === persistedConversationId) return
    let cancelled = false

    void openRuntimeConversation(persistedConversationId).then((conversation) => {
      if (conversation || cancelled) return
      void bindOverlayCompanionConversation(state.context_id, "").catch(() => undefined)
    })

    return () => {
      cancelled = true
    }
  }, [
    openRuntimeConversation,
    persistedConversationId,
    runtimeConversationId,
    state.context_id,
  ])

  useEffect(() => {
    document.documentElement.dataset.aitOverlayInteractive = "true"
    void desktop.overlay.setClickThrough(false)
    void desktop.overlay.focus()

    return () => {
      delete document.documentElement.dataset.aitOverlayInteractive
      void desktop.overlay.setClickThrough(readOverlayPreferences().clickThrough)
    }
  }, [])

  useEffect(() => {
    const composer = composerRef.current
    if (!composer) return
    composer.style.height = "0px"
    composer.style.height = `${overlayComposerHeight(composer.scrollHeight)}px`
  }, [runtime.draft])

  useEffect(() => {
    const scroll = messageScrollRef.current
    if (!scroll || !followTailRef.current) return
    scroll.scrollTop = scroll.scrollHeight
  }, [runtime.messages, runtime.activeRequestId])

  const handoffMutation = useMutation({
    mutationFn: (payload: CompanionHandoffRequest) => createCompanionHandoff(payload),
    onSuccess: async (handoff) => {
      await desktop.window.show()
      if (handoff.conversation_id) {
        try {
          await desktop.overlay.notifyCompanionNavigation({
            conversationId: handoff.conversation_id,
            handoffId: handoff.handoff_id,
          })
        } catch {
          // Backend handoff polling remains the recovery path if native event
          // delivery is unavailable during a dev reload or browser session.
        }
      }
      await desktop.window.focus()
    },
  })

  const recentMessages = runtime.messages.slice(-6)
  const latestAssistant = [...runtime.messages]
    .reverse()
    .find((message) => message.role === "assistant" && message.status === "complete")
  const latestRetryableAssistantIndex = runtime.messages.findLastIndex(
    (message) => message.role === "assistant" && (message.status === "error" || message.status === "cancelled"),
  )
  const retryUser = latestRetryableAssistantIndex >= 0
    ? previousCompanionUserMessage(runtime.messages, latestRetryableAssistantIndex)
    : null
  const peerSurface = runtime.ownerSurface === "main"
    ? "main chat"
    : runtime.ownerSurface === "overlay"
      ? "overlay"
      : "another window"

  function exitChat() {
    runtime.closeActiveStream()
    onClose()
  }

  function openMainChat() {
    if (runtime.activeRequestId !== null || runtime.openingConversation) return

    handoffMutation.mutate(
      buildOverlayChatHandoff(
        state,
        aiResult,
        latestAssistant?.content ?? "",
        runtime.conversationId,
      ),
    )
  }

  function jumpToLatest() {
    const scroll = messageScrollRef.current
    if (!scroll) return
    followTailRef.current = true
    setShowJumpToLatest(false)
    scroll.scrollTo({ top: scroll.scrollHeight, behavior: "smooth" })
  }

  function retryLastReply() {
    if (!retryUser || runtime.conversationBusyElsewhere || runtime.activeRequestId !== null) return
    void runtime.rewriteFromUser(retryUser, retryUser.content)
  }

  const mainChatLabel = handoffMutation.isPending
    ? "Opening…"
    : runtime.openingConversation
      ? "Restoring…"
      : runtime.activeRequestId !== null
        ? "Finish response first"
        : runtime.conversationId
          ? "Continue in main ↗"
          : "Open main chat ↗"

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
              <div className="flex items-center gap-1.5">
                <p className="text-xs font-semibold text-slate-100">AI Chat</p>
                {runtime.activeRequestId !== null && (
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-300" />
                )}
              </div>
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
          disabled={
            runtime.contextUpdating ||
            runtime.activeRequestId !== null ||
            runtime.openingConversation ||
            runtime.conversationBusyElsewhere
          }
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

      {runtime.conversationBusyElsewhere && (
        <div className="mx-3 mb-2 rounded-[12px] border border-amber-300/15 bg-amber-300/[0.07] px-3 py-2 text-[10px] text-amber-100/85">
          Replying in {peerSurface}… This view will refresh when the response finishes.
        </div>
      )}

      {aiResult && recentMessages.length === 0 && !runtime.openingConversation && (
        <div className="mx-3 mb-2.5 rounded-[14px] border border-cyan-300/10 bg-cyan-300/[0.055] px-3 py-2.5">
          <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-cyan-200/60">
            Existing AI result
          </p>
          <p className="mt-1.5 line-clamp-3 text-[11px] leading-4 text-slate-300">
            {aiResult.output_text}
          </p>
        </div>
      )}

      <div className="relative">
        <div
          ref={messageScrollRef}
          className="h-[220px] overflow-y-auto px-3 py-2"
          onScroll={(event) => {
            const nearTail = overlayChatIsNearTail(event.currentTarget)
            followTailRef.current = nearTail
            setShowJumpToLatest(!nearTail)
          }}
        >
          {runtime.openingConversation ? (
            <div className="flex h-full items-center justify-center gap-2 text-[10px] text-slate-500">
              <span className="h-3 w-3 animate-spin rounded-full border border-white/20 border-t-white/70" />
              Restoring conversation…
            </div>
          ) : recentMessages.length === 0 ? (
            <div className="flex h-full items-center justify-center px-5 text-center">
              <div>
                <p className="text-xs font-medium text-slate-300">Ask about this selection</p>
                <p className="mt-1.5 text-[10px] leading-4 text-slate-500">
                  The selection, translation, and bounded nearby context are attached automatically.
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
                      <div className="max-w-none break-words [&_blockquote]:border-l [&_blockquote]:border-white/15 [&_blockquote]:pl-2 [&_code]:rounded [&_code]:bg-black/20 [&_code]:px-1 [&_li]:my-0.5 [&_ol]:my-1.5 [&_ol]:pl-4 [&_p]:my-1 [&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-black/20 [&_pre]:p-2 [&_ul]:my-1.5 [&_ul]:pl-4">
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

        {showJumpToLatest && (
          <button
            type="button"
            className="absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full border border-white/10 bg-slate-950/90 px-2.5 py-1 text-[9px] font-medium text-slate-300 shadow-lg backdrop-blur"
            onClick={jumpToLatest}
          >
            ↓ Latest
          </button>
        )}
      </div>

      {runtime.errorMessage && (
        <div className="mx-3 mb-2 flex items-center justify-between gap-2 rounded-[12px] border border-rose-300/15 bg-rose-300/[0.08] px-3 py-2 text-[10px] leading-4 text-rose-200">
          <span>{runtime.errorMessage}</span>
          {retryUser && !runtime.conversationBusyElsewhere && (
            <button
              type="button"
              className="shrink-0 rounded-full border border-rose-200/15 px-2 py-0.5 font-medium hover:bg-rose-200/10"
              onClick={retryLastReply}
            >
              Retry
            </button>
          )}
        </div>
      )}

      {!runtime.chatAvailable && runtime.chatStatusLoaded && (
        <p className="mx-3 mb-2 rounded-[12px] border border-amber-300/15 bg-amber-300/[0.07] px-3 py-2 text-[10px] leading-4 text-amber-100/80">
          AI Chat unavailable · {runtime.chatStatusDetail}
        </p>
      )}

      <div className="border-t border-white/[0.07] px-3 py-2.5">
        <div className="flex items-end gap-2">
          <textarea
            ref={composerRef}
            autoFocus
            rows={1}
            value={runtime.draft}
            disabled={runtime.openingConversation || runtime.conversationBusyElsewhere}
            placeholder={runtime.openingConversation
              ? "Restoring conversation…"
              : runtime.conversationBusyElsewhere
                ? `Replying in ${peerSurface}…`
                : runtime.activeRequestId === null
                  ? "Ask a follow-up…"
                  : "Generating…"}
            className="min-h-9 flex-1 resize-none overflow-y-auto rounded-[13px] border border-white/[0.08] bg-white/[0.055] px-3 py-2 text-[11px] leading-4 text-slate-100 outline-none placeholder:text-slate-600 focus:border-white/[0.16] focus:bg-white/[0.07] disabled:opacity-50"
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
              disabled={
                !runtime.chatAvailable ||
                !runtime.draft.trim() ||
                runtime.openingConversation ||
                runtime.conversationBusyElsewhere
              }
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
            disabled={
              handoffMutation.isPending ||
              runtime.activeRequestId !== null ||
              runtime.openingConversation
            }
            className="text-[9px] font-medium text-slate-500 hover:text-slate-300 disabled:opacity-40"
            onClick={openMainChat}
          >
            {mainChatLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
