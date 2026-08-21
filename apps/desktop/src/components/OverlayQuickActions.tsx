import { useEffect, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import {
  getQuickActionStatus,
  runQuickAction,
  saveResearchNote,
} from "../api/quick-actions"
import type {
  OverlayStateResponse,
  QuickActionKey,
  QuickActionRequest,
  QuickActionResponse,
  ResearchNoteSaveRequest,
} from "../api/types"
import { subscribeOverlayCommands } from "../desktop/overlay-commands"
import type { OverlayActionPresentation } from "../desktop/overlay-sizing"
import OverlayCompactChat from "./OverlayCompactChat"

type ActionSpec = {
  key: QuickActionKey
  label: string
  title: string
}

type ActionVariables = {
  contextId: string
  payload: QuickActionRequest
}

type NoteVariables = {
  contextId: string
  payload: ResearchNoteSaveRequest
}

type ResultState = {
  contextId: string
  result: QuickActionResponse
}

type FeedbackState = {
  contextId: string
  message: string
}

type ResultView = "translation" | "ai"
export type OverlayCompletedInteraction = "copy" | "handoff"

const actions: ActionSpec[] = [
  { key: "reading_context_translate", label: "译", title: "结合当前阅读上下文 AI 翻译" },
  { key: "ai_polish", label: "润色", title: "保持原意和原语言进行 AI 润色" },
  { key: "reading_explain", label: "解释", title: "结合上下文解释选中内容" },
  { key: "reading_summarize", label: "总结", title: "总结当前选中的内容" },
  { key: "reading_section_role", label: "段落", title: "分析这段内容在当前章节中的作用" },
]

const primaryActions = actions.slice(0, 4)
const secondaryAction = actions[4]

const actionLabels: Record<QuickActionKey, string> = {
  ai_polish: "AI 润色",
  reading_context_translate: "上下文翻译",
  reading_explain: "解释",
  reading_summarize: "总结",
  reading_section_role: "段落作用",
}

function baseContext(state: OverlayStateResponse) {
  return {
    source_text: state.source_text,
    translated_text: state.translated_text,
    source_language: state.source_language,
    target_language: state.target_language,
    resource_url: state.resource_url,
    resource_title: state.resource_title,
    section_heading: state.section_heading,
    context_before: state.context_before,
    context_after: state.context_after,
    source_kind: state.source_kind || "desktop",
  }
}

export default function OverlayQuickActions({
  state,
  onPresentationChange,
  onCompletedInteraction,
}: {
  state: OverlayStateResponse
  onPresentationChange?: (presentation: OverlayActionPresentation) => void
  onCompletedInteraction?: (interaction: OverlayCompletedInteraction) => void
}) {
  const [resultState, setResultState] = useState<ResultState | null>(null)
  const [resultOpen, setResultOpen] = useState(false)
  const [feedback, setFeedback] = useState<FeedbackState | null>(null)
  const [copied, setCopied] = useState(false)
  const [resultView, setResultView] = useState<ResultView>("translation")
  const [moreOpen, setMoreOpen] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)

  const statusQuery = useQuery({
    queryKey: ["quick-action-status"],
    queryFn: getQuickActionStatus,
    staleTime: 30_000,
    retry: 0,
  })

  const activeResult = resultState?.contextId === state.context_id ? resultState.result : null
  const activeFeedback = feedback?.contextId === state.context_id ? feedback.message : ""
  const aiAvailable = statusQuery.data?.available ?? false

  function setPresentation(presentation: OverlayActionPresentation) {
    onPresentationChange?.(presentation)
  }

  function collapseTransientPanels() {
    setMoreOpen(false)
    setResultOpen(false)
    setChatOpen(false)
    setPresentation("compact")
  }

  const actionMutation = useMutation({
    mutationFn: ({ payload }: ActionVariables) => runQuickAction(payload),
    onMutate: ({ contextId }) => {
      if (contextId !== state.context_id) return
      collapseTransientPanels()
      setFeedback(null)
      setCopied(false)
    },
    onSuccess: (result, variables) => {
      if (variables.contextId !== state.context_id) return
      setResultState({ contextId: variables.contextId, result })
      setResultView("ai")
      setResultOpen(true)
      setPresentation("result")
      setCopied(false)
    },
    onError: (error, variables) => {
      if (variables.contextId !== state.context_id) return
      setFeedback({
        contextId: variables.contextId,
        message: error instanceof Error ? error.message : "Quick action failed.",
      })
    },
  })

  const noteMutation = useMutation({
    mutationFn: ({ payload }: NoteVariables) => saveResearchNote(payload),
    onMutate: ({ contextId }) => {
      if (contextId !== state.context_id) return
      setFeedback(null)
    },
    onSuccess: (result, variables) => {
      if (variables.contextId !== state.context_id) return
      setFeedback({
        contextId: variables.contextId,
        message: result.created ? "已加入研究笔记" : "研究笔记已更新",
      })
    },
    onError: (error, variables) => {
      if (variables.contextId !== state.context_id) return
      setFeedback({
        contextId: variables.contextId,
        message: error instanceof Error ? error.message : "Unable to save research note.",
      })
    },
  })

  function runAction(action: QuickActionKey) {
    actionMutation.mutate({
      contextId: state.context_id,
      payload: {
        ...baseContext(state),
        action,
        style: "academic",
      },
    })
  }

  function saveNote() {
    noteMutation.mutate({
      contextId: state.context_id,
      payload: {
        ...baseContext(state),
        ai_content: activeResult?.output_text ?? "",
        ai_action: activeResult?.action ?? "",
      },
    })
  }

  function openChat() {
    setFeedback(null)
    setResultOpen(false)
    setMoreOpen(false)
    setChatOpen(true)
    setPresentation("chat")
  }

  function closeChat() {
    setChatOpen(false)
    setPresentation("compact")
  }

  function toggleMore() {
    if (resultOpen) setResultOpen(false)
    const next = !moreOpen
    setMoreOpen(next)
    setPresentation(next ? "expanded" : "compact")
  }

  function closeResult() {
    setResultOpen(false)
    setPresentation(moreOpen ? "expanded" : "compact")
  }

  async function copyActiveView() {
    const text =
      resultView === "ai"
        ? activeResult?.output_text ?? ""
        : state.translated_text
    if (!text) return

    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      onCompletedInteraction?.("copy")
      window.setTimeout(() => setCopied(false), 900)
    } catch {
      setCopied(false)
    }
  }

  const busy = actionMutation.isPending || noteMutation.isPending
  const activeAction = activeResult?.action ?? null

  useEffect(() => subscribeOverlayCommands((command) => {
    if (command === "escape") {
      if (chatOpen) {
        closeChat()
      } else if (resultOpen) {
        closeResult()
      } else if (moreOpen) {
        setMoreOpen(false)
        setPresentation("compact")
      }
      return
    }

    if (command === "copy") {
      if (resultOpen && activeResult) void copyActiveView()
      return
    }

    if (command === "more") {
      if (!busy && !chatOpen) toggleMore()
      return
    }

    if (chatOpen || !aiAvailable || busy) return
    const index = Number(command.slice(-1)) - 1
    const action = primaryActions[index]
    if (action) runAction(action.key)
  }), [activeResult, aiAvailable, busy, chatOpen, moreOpen, resultOpen, resultView])

  if (state.phase !== "ready") return null

  return (
    <section className={`ait-overlay-action-surface relative border-t border-white/10 ${resultOpen && activeResult ? "is-result-open" : ""} ${moreOpen ? "is-more-open" : ""} ${chatOpen ? "is-chat-open" : ""}`}>
      {chatOpen ? (
        <OverlayCompactChat
          state={state}
          aiResult={activeResult}
          onClose={closeChat}
        />
      ) : (
        <>
          <div className="ait-overlay-result-morph">
            <div className="ait-overlay-result-morph-inner">
              {activeResult && (
                <div className="border-b border-white/10 px-3 pb-3 pt-2.5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="ait-overlay-result-tabs flex items-center gap-1 rounded-full p-0.5">
                      <ViewTab
                        active={resultView === "translation"}
                        label="译文"
                        onClick={() => {
                          setResultView("translation")
                          setCopied(false)
                        }}
                      />
                      <ViewTab
                        active={resultView === "ai"}
                        label="AI 结果"
                        onClick={() => {
                          setResultView("ai")
                          setCopied(false)
                        }}
                      />
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        className="ait-overlay-quiet-button rounded-full px-2.5 py-1 text-[10px]"
                        onClick={openChat}
                      >
                        追问
                      </button>
                      <button
                        type="button"
                        aria-live="polite"
                        className={`ait-overlay-quiet-button rounded-full px-2.5 py-1 text-[10px] ${copied ? "is-copied" : ""}`}
                        onClick={() => void copyActiveView()}
                      >
                        {copied ? "✓ 已复制" : "复制"}
                      </button>
                      <button
                        type="button"
                        aria-label="Collapse AI result"
                        className="ait-overlay-quiet-button flex h-6 w-6 items-center justify-center rounded-full text-xs"
                        onClick={closeResult}
                      >
                        ×
                      </button>
                    </div>
                  </div>

                  <div className="ait-overlay-result-content mt-2.5 max-h-[150px] overflow-y-auto pr-1">
                    {resultView === "ai" ? (
                      <>
                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                          {actionLabels[activeResult.action]} · {activeResult.provider} / {activeResult.model}
                        </p>
                        <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-200">
                          {activeResult.output_text}
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Translation · {state.provider || "provider"}
                        </p>
                        <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-200">
                          {state.translated_text}
                        </p>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {activeFeedback && !busy && (
            <div className="ait-overlay-action-toast pointer-events-none absolute inset-x-3 bottom-[58px] z-20 rounded-full px-3 py-1.5 text-center text-[10px]">
              {activeFeedback}
            </div>
          )}

          <div className="ait-overlay-action-bar flex items-center gap-1.5 px-3 py-2.5">
            <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
              {primaryActions.map((action, index) => (
                <ActionButton
                  key={action.key}
                  active={activeAction === action.key && resultOpen}
                  disabled={!aiAvailable || busy}
                  label={action.label}
                  title={`${aiAvailable ? action.title : statusQuery.data?.detail || "AI provider is not configured"} · ${index + 1}`}
                  onClick={() => runAction(action.key)}
                />
              ))}
            </div>

            <div className="h-5 w-px shrink-0 bg-white/10" />

            <button
              type="button"
              aria-label="More contextual actions"
              aria-expanded={moreOpen}
              title="更多操作 · M"
              disabled={busy}
              className={`ait-overlay-action-button relative flex h-8 min-w-9 shrink-0 items-center justify-center rounded-full px-2 text-sm ${moreOpen ? "is-active" : ""}`}
              onClick={toggleMore}
            >
              {busy ? (
                <span className="h-3 w-3 animate-spin rounded-full border border-white/20 border-t-white/70" />
              ) : (
                <span className="tracking-[0.12em]">•••</span>
              )}
              {!aiAvailable && statusQuery.isSuccess && (
                <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-amber-300/70" />
              )}
            </button>
          </div>

          <div className="ait-overlay-more-morph">
            <div className="ait-overlay-more-morph-inner">
              <div className="flex items-center gap-1.5 border-t border-white/10 px-3 py-2.5">
                {secondaryAction && (
                  <ActionButton
                    active={activeAction === secondaryAction.key && resultOpen}
                    disabled={!aiAvailable || busy}
                    label={secondaryAction.label}
                    title={
                      aiAvailable
                        ? secondaryAction.title
                        : statusQuery.data?.detail || "AI provider is not configured"
                    }
                    onClick={() => runAction(secondaryAction.key)}
                  />
                )}
                <ActionButton
                  disabled={busy}
                  label="笔记"
                  title="加入研究笔记"
                  onClick={saveNote}
                />
                <ActionButton
                  disabled={!aiAvailable || busy}
                  label="AI Chat"
                  title="在悬浮窗中继续 AI Chat"
                  onClick={openChat}
                  wide
                />
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  )
}

function ActionButton({
  label,
  title,
  active = false,
  disabled = false,
  wide = false,
  onClick,
}: {
  label: string
  title: string
  active?: boolean
  disabled?: boolean
  wide?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      className={`ait-overlay-action-button shrink-0 rounded-full px-3 py-1.5 text-[11px] font-medium ${wide ? "px-3.5" : ""} ${active ? "is-active" : ""}`}
      onClick={onClick}
    >
      {label}
    </button>
  )
}

function ViewTab({
  active,
  label,
  onClick,
}: {
  active: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={`rounded-full px-2.5 py-1 text-[10px] font-medium transition ${
        active
          ? "bg-white/10 text-white"
          : "text-slate-500 hover:text-slate-300"
      }`}
      onClick={onClick}
    >
      {label}
    </button>
  )
}
