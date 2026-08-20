import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { createCompanionHandoff } from "../api/companion"
import {
  getQuickActionStatus,
  runQuickAction,
  saveResearchNote,
} from "../api/quick-actions"
import type {
  CompanionHandoffRequest,
  OverlayStateResponse,
  QuickActionKey,
  QuickActionRequest,
  QuickActionResponse,
  ResearchNoteSaveRequest,
} from "../api/types"
import { desktop } from "../desktop"

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

type HandoffVariables = {
  contextId: string
  payload: CompanionHandoffRequest
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

const actions: ActionSpec[] = [
  { key: "reading_context_translate", label: "译", title: "结合当前阅读上下文 AI 翻译" },
  { key: "ai_polish", label: "润色", title: "保持原意和原语言进行 AI 润色" },
  { key: "reading_explain", label: "解释", title: "结合上下文解释选中内容" },
  { key: "reading_summarize", label: "总结", title: "总结当前选中的内容" },
  { key: "reading_section_role", label: "段落", title: "分析这段内容在当前章节中的作用" },
]

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
    source_kind: state.source_kind || "browser_selection",
  }
}

export default function OverlayQuickActions({ state }: { state: OverlayStateResponse }) {
  const [resultState, setResultState] = useState<ResultState | null>(null)
  const [feedback, setFeedback] = useState<FeedbackState | null>(null)
  const [copied, setCopied] = useState(false)
  const [resultView, setResultView] = useState<ResultView>("translation")

  const statusQuery = useQuery({
    queryKey: ["quick-action-status"],
    queryFn: getQuickActionStatus,
    staleTime: 30_000,
    retry: 0,
  })

  const activeResult = resultState?.contextId === state.context_id ? resultState.result : null
  const activeFeedback = feedback?.contextId === state.context_id ? feedback.message : ""
  const aiAvailable = statusQuery.data?.available ?? false

  const actionMutation = useMutation({
    mutationFn: ({ payload }: ActionVariables) => runQuickAction(payload),
    onMutate: ({ contextId }) => {
      if (contextId !== state.context_id) return
      setFeedback(null)
      setCopied(false)
    },
    onSuccess: (result, variables) => {
      if (variables.contextId !== state.context_id) return
      setResultState({ contextId: variables.contextId, result })
      setResultView("ai")
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

  const handoffMutation = useMutation({
    mutationFn: ({ payload }: HandoffVariables) => createCompanionHandoff(payload),
    onMutate: ({ contextId }) => {
      if (contextId !== state.context_id) return
      setFeedback(null)
    },
    onSuccess: async (_result, variables) => {
      if (variables.contextId !== state.context_id) return
      setFeedback({
        contextId: variables.contextId,
        message: "已将当前内容交给 AI Chat",
      })
      try {
        await desktop.window.show()
        await desktop.window.focus()
      } catch {
        setFeedback({
          contextId: variables.contextId,
          message: "上下文已交给 AI Chat，但主窗口聚焦失败。",
        })
      }
    },
    onError: (error, variables) => {
      if (variables.contextId !== state.context_id) return
      setFeedback({
        contextId: variables.contextId,
        message: error instanceof Error ? error.message : "Unable to open AI Chat.",
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
    handoffMutation.mutate({
      contextId: state.context_id,
      payload: {
        ...baseContext(state),
        ai_content: activeResult?.output_text ?? "",
        ai_action: activeResult?.action ?? "",
        suggested_prompt: activeResult
          ? "请基于当前划词内容、译文和已有 AI 结果继续分析。"
          : "",
      },
    })
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
      window.setTimeout(() => setCopied(false), 900)
    } catch {
      setCopied(false)
    }
  }

  if (state.phase !== "ready") return null

  const busy =
    actionMutation.isPending ||
    noteMutation.isPending ||
    handoffMutation.isPending

  return (
    <section className="border-t border-white/10 px-4 py-3">
      {activeResult && (
        <div className="mb-3 overflow-hidden rounded-xl border border-cyan-300/15 bg-cyan-300/[0.06]">
          <div className="flex items-center justify-between gap-3 border-b border-white/10 px-3 py-2">
            <div className="flex items-center gap-1 rounded-lg bg-black/10 p-0.5">
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
                className="rounded-md px-2 py-1 text-[10px] text-slate-400 hover:bg-white/10 hover:text-white"
                onClick={() => void copyActiveView()}
              >
                {copied ? "已复制" : "复制"}
              </button>
              <button
                type="button"
                className="rounded-md px-2 py-1 text-[10px] text-slate-500 hover:bg-white/10 hover:text-white"
                onClick={() => {
                  setResultState(null)
                  setResultView("translation")
                }}
              >
                收起
              </button>
            </div>
          </div>

          <div className="p-3">
            {resultView === "ai" ? (
              <>
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-200/70">
                  {actionLabels[activeResult.action]} · {activeResult.provider} / {activeResult.model}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-200">
                  {activeResult.output_text}
                </p>
              </>
            ) : (
              <>
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Deterministic translation · {state.provider || "translation provider"}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-200">
                  {state.translated_text}
                </p>
              </>
            )}
          </div>
        </div>
      )}

      {busy && (
        <div className="mb-2 flex items-center gap-2 text-[11px] text-slate-400">
          <span className="h-3 w-3 animate-spin rounded-full border border-slate-600 border-t-slate-300" />
          {noteMutation.isPending
            ? "正在保存笔记…"
            : handoffMutation.isPending
              ? "正在准备 AI Chat 上下文…"
              : "AI 正在处理…"}
        </div>
      )}

      {activeFeedback && !busy && (
        <p className="mb-2 rounded-lg bg-white/5 px-2.5 py-1.5 text-[11px] leading-4 text-slate-400">
          {activeFeedback}
        </p>
      )}

      <div className="flex flex-wrap gap-1.5">
        {actions.map((action) => (
          <button
            key={action.key}
            type="button"
            title={
              aiAvailable
                ? action.title
                : statusQuery.data?.detail || "AI provider is not configured"
            }
            disabled={!aiAvailable || busy}
            className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[11px] font-medium text-slate-300 transition hover:border-cyan-300/30 hover:bg-cyan-300/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
            onClick={() => runAction(action.key)}
          >
            {action.label}
          </button>
        ))}
        <button
          type="button"
          title="加入研究笔记"
          disabled={busy}
          className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[11px] font-medium text-slate-300 transition hover:border-emerald-300/30 hover:bg-emerald-300/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
          onClick={saveNote}
        >
          笔记
        </button>
        <button
          type="button"
          title="在主窗口继续 AI Chat"
          disabled={busy}
          className="rounded-lg border border-violet-300/20 bg-violet-300/[0.06] px-2.5 py-1.5 text-[11px] font-medium text-violet-200 transition hover:border-violet-300/40 hover:bg-violet-300/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
          onClick={openChat}
        >
          AI Chat
        </button>
      </div>

      {!aiAvailable && statusQuery.isSuccess && (
        <p className="mt-2 line-clamp-2 text-[10px] leading-4 text-amber-300/70">
          AI Quick Actions 未配置：{statusQuery.data.detail}
        </p>
      )}
    </section>
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
      className={`rounded-md px-2.5 py-1 text-[10px] font-medium transition ${
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
