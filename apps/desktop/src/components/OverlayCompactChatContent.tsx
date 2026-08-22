import { useEffect, useRef, useState } from "react"
import { useMutation } from "@tanstack/react-query"
import ReactMarkdown from "react-markdown"

import { createCompanionHandoff } from "../api/companion"
import { bindOverlayCompanionConversation, presentOverlay, showOverlayError } from "../api/overlay"
import { translateTextWithFallback } from "../api/translation"
import type {
  CompanionHandoffRequest,
  OverlayStateResponse,
  QuickActionResponse,
} from "../api/types"
import { desktop } from "../desktop"
import { readOverlayPreferences } from "../desktop/overlay-preferences"
import { previousCompanionUserMessage } from "../features/companion/companion-runtime"
import { companionRecoveryLabel } from "../features/companion/companion-recovery"
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

const TRANSLATION_INTENT_PATTERNS = [
  /^翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^帮我翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^我要你翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^请翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^translate(?: this| it| the selection)?[.! ]*$/i,
  /^please translate(?: this| it| the selection)?[.! ]*$/i,
]

function isExplicitTranslationIntent(value: string): boolean {
  const normalized = value.trim()
  return Boolean(normalized) && TRANSLATION_INTENT_PATTERNS.some((pattern) => pattern.test(normalized))
}

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
  const syncedTranslationRef = useRef("")
  const [showJumpToLatest, setShowJumpToLatest] = useState(false)
  const [translationHandoffBusy, setTranslationHandoffBusy] = useState(false)
  const context = contextFromOverlay(state, aiResult)
  const persistedConversationId = overlayCompanionConversationId(state)
  const runtime = useCompanionConversationRuntime({
    initialContext: context,
    initialContextMode: "reading",
    // A fresh external selection replaces the composer wholesale. Because the
    // parent is keyed by context_id, every new selection creates a new runtime
    // seed instead of appending to a stale user draft.
    initialDraft: state.source_text,
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
    document.documentElement.dataset.aitSelectionScope = "internal"
    void desktop.overlay.setClickThrough(false)
    void desktop.overlay.focus()

    return () => {
      delete document.documentElement.dataset.aitOverlayInteractive
      delete document.documentElement.dataset.aitSelectionScope
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

  useEffect(() => {
    const translatedText = state.translated_text.trim()
    if (!translatedText || runtime.activeRequestId !== null || runtime.contextUpdating) return
    if (
      runtime.context.source_text === state.source_text &&
      runtime.context.translated_text === state.translated_text
    ) {
      return
    }

    const signature = `${state.context_id}\u001f${state.translated_text}`
    if (syncedTranslationRef.current === signature) return
    syncedTranslationRef.current = signature

    // Translation is a presentation mode of the same reading interaction, not
    // a new selection. Once the in-flight chat reply reaches a safe boundary,
    // update the existing conversation context so follow-up AI turns can see
    // the translated text without remounting or clearing the composer.
    void runtime.attachReadingContext(context)
  }, [
    context,
    runtime.activeRequestId,
    runtime.attachReadingContext,
    runtime.context.source_text,
    runtime.context.translated_text,
    runtime.contextUpdating,
    state.context_id,
    state.source_text,
    state.translated_text,
  ])

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
  const recoveryLabel = companionRecoveryLabel(
    runtime.recoveryState,
    Boolean(runtime.conversationId || persistedConversationId),
  )

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

  async function runTranslationHandoff(userMessage: string) {
    if (translationHandoffBusy || !state.source_text.trim()) return
    setTranslationHandoffBusy(true)

    // Keep the command in the normal AI conversation. Translation itself uses
    // the frozen reading source, never the command text in the composer.
    runtime.sendMessage(userMessage)

    try {
      const result = await translateTextWithFallback({
        source_text: state.source_text,
        source_language: state.source_language,
        target_language: state.target_language,
      })
      await presentOverlay({
        context_id: state.context_id,
        source_text: result.source_text,
        translated_text: result.translated_text,
        source_language: result.source_language,
        target_language: result.target_language,
        provider: result.provider === "ai" && result.model ? `ai/${result.model}` : result.provider,
        translation_notice: result.notice,
        resource_url: state.resource_url,
        resource_title: state.resource_title,
        section_heading: state.section_heading,
        context_before: state.context_before,
        context_after: state.context_after,
        source_kind: state.source_kind,
      })
    } catch (error) {
      await showOverlayError({
        context_id: state.context_id,
        source_text: state.source_text,
        source_language: state.source_language,
        target_language: state.target_language,
        message: error instanceof Error ? error.message : "Translation failed.",
        resource_url: state.resource_url,
        resource_title: state.resource_title,
        section_heading: state.section_heading,
        context_before: state.context_before,
        context_after: state.context_after,
        source_kind: state.source_kind,
      }).catch(() => undefined)
    } finally {
      setTranslationHandoffBusy(false)
    }
  }

  function submitComposer() {
    const message = runtime.draft.trim()
    if (!message) return
    if (isExplicitTranslationIntent(message)) {
      void runTranslationHandoff(message)
      return
    }
    runtime.sendMessage()
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

  const recovering = runtime.recoveryState === "recovering"

  return (
    <div className="border-b border-white/10 bg-black/10" data-ait-selection-scope="internal">
      <div className="flex items-center justify-between gap-3 px-3 py-2.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <button
              type="button"
              data-tauri-drag-region="false"
              aria-label="Back to translation"
              className="ait-overlay-quiet-button flex h-7 w-7 items-center justify-center rounded-full text-sm text-slate-300"
              onClick={exitChat}
            >
              ‹
            </button>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <p className="text-xs font-semibold text-slate-100">AI Chat</p>
                {(runtime.activeRequestId !== null || translationHandoffBusy) && (
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
          data-tauri-drag-region="false"
          disabled={
            runtime.contextUpdating ||
            runtime.activeRequestId !== null ||
            runtime.openingConversation ||
            runtime.conversationBusyElsewhere ||
            recovering
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

      {runtime.recoveryState !== "idle" && recoveryLabel && (
        <div className={`mx-3 mb-2 flex items-center justify-between gap-2 rounded-[12px] border px-3 py-2 text-[10px] leading-4 ${
          runtime.recoveryState === "recovering"
            ? "border-cyan-300/15 bg-cyan-300/[0.06] text-cyan-100/85"
            : "border-amber-300/15 bg-amber-300/[0.07] text-amber-100/85"
        }`}>
          <div className="min-w-0">
            <p>{recoveryLabel}</p>
            {runtime.recoveryDetail && runtime.recoveryDetail !== recoveryLabel && (
              <p className="mt-0.5 truncate opacity-65">{runtime.recoveryDetail}</p>
            )}
          </div>
          {runtime.recoveryState === "offline" && (
            <button type="button" data-tauri-drag-region="false" className="shrink-0 rounded-full border border-current/15 px-2 py-0.5 font-medium hover:bg-white/[0.06]" onClick={() => void runtime.retryRecovery()}>Retry</button>
          )}
        </div>
      )}

      {aiResult && recentMessages.length === 0 && !runtime.openingConversation && (
        <div className="mx-3 mb-2.5 rounded-[14px] border border-cyan-300/10 bg-cyan-300/[0.055] px-3 py-2.5">
          <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-cyan-200/60">Existing AI result</p>
          <p className="mt-1.5 line-clamp-3 text-[11px] leading-4 text-slate-300">{aiResult.output_text}</p>
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
                <p className="mt-1.5 text-[10px] leading-4 text-slate-500">The selection and bounded nearby context are attached automatically.</p>
              </div>
            </div>
          ) : (
            <div className="space-y-2.5">
              {recentMessages.map((message) => (
                <div key={message.id} className={message.role === "user" ? "ml-auto max-w-[84%] rounded-[15px] bg-white/[0.11] px-3 py-2 text-[11px] leading-4 text-slate-100" : "max-w-[92%] rounded-[15px] border border-white/[0.07] bg-white/[0.035] px-3 py-2 text-[11px] leading-4 text-slate-300"}>
                  {message.role === "assistant" ? (
                    message.content ? (
                      <div className="max-w-none break-words [&_blockquote]:border-l [&_blockquote]:border-white/15 [&_blockquote]:pl-2 [&_code]:rounded [&_code]:bg-black/20 [&_code]:px-1 [&_li]:my-0.5 [&_ol]:my-1.5 [&_ol]:pl-4 [&_p]:my-1 [&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-black/20 [&_pre]:p-2 [&_ul]:my-1.5 [&_ul]:pl-4"><ReactMarkdown>{message.content}</ReactMarkdown></div>
                    ) : message.status === "streaming" ? (
                      <div className="flex items-center gap-2 text-slate-500"><span className="h-3 w-3 animate-spin rounded-full border border-white/20 border-t-white/70" />Thinking…</div>
                    ) : <span className="text-slate-500">No response content.</span>
                  ) : <p className="whitespace-pre-wrap">{message.content}</p>}
                </div>
              ))}
            </div>
          )}
        </div>

        {showJumpToLatest && (
          <button type="button" data-tauri-drag-region="false" className="absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full border border-white/10 bg-slate-950/90 px-2.5 py-1 text-[9px] font-medium text-slate-300 shadow-lg backdrop-blur" onClick={jumpToLatest}>↓ Latest</button>
        )}
      </div>

      {runtime.errorMessage && runtime.recoveryState === "idle" && (
        <div className="mx-3 mb-2 flex items-center justify-between gap-2 rounded-[12px] border border-rose-300/15 bg-rose-300/[0.08] px-3 py-2 text-[10px] leading-4 text-rose-200">
          <span>{runtime.errorMessage}</span>
          {retryUser && !runtime.conversationBusyElsewhere && <button type="button" data-tauri-drag-region="false" className="shrink-0 rounded-full border border-rose-200/15 px-2 py-0.5 font-medium hover:bg-rose-200/10" onClick={retryLastReply}>Retry</button>}
        </div>
      )}

      {!runtime.chatAvailable && runtime.chatStatusLoaded && runtime.recoveryState === "idle" && (
        <p className="mx-3 mb-2 rounded-[12px] border border-amber-300/15 bg-amber-300/[0.07] px-3 py-2 text-[10px] leading-4 text-amber-100/80">AI Chat unavailable · {runtime.chatStatusDetail}</p>
      )}

      <div className="border-t border-white/[0.07] px-3 py-2.5">
        <div className="flex items-end gap-2">
          <textarea
            ref={composerRef}
            autoFocus
            rows={1}
            value={runtime.draft}
            disabled={runtime.openingConversation || runtime.conversationBusyElsewhere || recovering || translationHandoffBusy}
            placeholder={runtime.openingConversation || recovering ? "Recovering conversation…" : runtime.conversationBusyElsewhere ? `Replying in ${peerSurface}…` : translationHandoffBusy ? "Translating selection…" : runtime.activeRequestId === null ? "Ask a follow-up…" : "Generating…"}
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
                submitComposer()
              }
            }}
          />
          {runtime.activeRequestId !== null ? (
            <button type="button" data-tauri-drag-region="false" title="Stop generation" className="ait-overlay-action-button flex h-9 w-9 items-center justify-center rounded-full text-xs text-rose-200" onClick={runtime.cancelStream}>■</button>
          ) : (
            <button type="button" data-tauri-drag-region="false" title="Send · Enter" disabled={!runtime.chatAvailable || !runtime.draft.trim() || runtime.openingConversation || runtime.conversationBusyElsewhere || recovering || translationHandoffBusy} className="ait-overlay-action-button flex h-9 w-9 items-center justify-center rounded-full text-sm disabled:opacity-35" onClick={submitComposer}>↑</button>
          )}
        </div>

        <div className="mt-2 flex items-center justify-between gap-3">
          <span className="text-[9px] text-slate-600">Enter send · Shift+Enter newline · Esc back</span>
          <button type="button" data-tauri-drag-region="false" disabled={handoffMutation.isPending || runtime.activeRequestId !== null || runtime.openingConversation || recovering} className="text-[9px] font-medium text-slate-500 hover:text-slate-300 disabled:opacity-40" onClick={openMainChat}>{mainChatLabel}</button>
        </div>
      </div>
    </div>
  )
}
