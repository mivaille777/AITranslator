import { useState } from "react"
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

type ActionSpec = {
  key: QuickActionKey
  label: string
  title: string
}

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

type ResultState = {
  contextId: string
  result: QuickActionResponse
}

type FeedbackState = {
  contextId: string
  message: string
}

type ActionVariables = {
  contextId: string
  payload: QuickActionRequest
}

type NoteVariables = {
  contextId: string
  payload: ResearchNoteSaveRequest
}

export default function OverlayQuickActions({ state }: { state: OverlayStateResponse }) {
  const [resultState, setResultState] = useState<ResultState | null>(null)
  const [feedback, setFeedback] = useState<FeedbackState | null>(null)
  const [copied, setCopied] = useState(false)

  const statusQuery = useQuery({
    queryKey: ["quick-action-status"],
    queryFn: getQuickActionStatus,
    staleTime: 30_000,
    retry: 0,
  })

  const activeResult = resultState?.contextId === state.context_id ? resultState.result : null
  const activeFeedback = feedback?.contextId === state.context_id ? feedback.message : ""
  const aiAvailable = statusQuery.data?.available ?? false

  function actionVariables(action: QuickActionKey): ActionVariables {
    return {
      contextId: state.context_id,
      payload: {
        action,
        source_text: state.source_text,
        translated_text: state.translated_text,
        source_language: state.source_language,
        target_language: state.target_language,
        style: "academic",
        resource_url: state.resource_url,
        resource_title: state.resource_title,
        section_heading: state.section_heading,
        context_before: state.context_before,
        context_after: state.context_after,
        source_kind: state.source_kind || "browser_selection",
      },
    }
  }

  function noteVariables(): NoteVariables {
    return {
      contextId: state.context_id,
      payload: {
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
        ai_content: activeResult?.output_text ?? "",
        ai_action: activeResult?.action ?? "",
      },
    }
  }

  const actionMutation = useMutation({
    mutationFn: ({ payload }: ActionVariables) => runQuickAction(payload),
    onMutate: () => {
      setFeedback(null)
      setCopied(false)
    },
    onSuccess: (result, variables) => {
      setResultState({ contextId: variables.contextId, result })
    },
    onError: (error, variables) => {
      setFeedback({
        contextId: variables.contextId,
        message: error instanceof Error ? error.message : "Quick action failed.",
      })
    },
  })

  const noteMutation = useMutation({
    mutationFn: ({ payload }: NoteVariables) => saveResearchNote(payload),
    onSuccess: (result, variables) => {
      setFeedback({
        contextId: variables.contextId,
        message: result.created ? "已加入研究笔记" : "研究笔记已更新",
      })
    },
    onError: (error, variables) => {
      setFeedback({
        contextId: variables.contextId,
        message: error instanceof Error ? error.message : "Unable to save research note.",
      })
    },
  })

  async function copyResult() {
    if (!activeResult?.output_text) return
    try {
      await navigator.clipboard.writeText(activeResult.output_text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 900)
    } catch {
      setCopied(false)
    }
  }

  if (state.phase !== "ready") return null

  return (
    <section className="border-t border-white/10 px-4 py-3">
      {activeResult && (
        <div className="mb-3 rounded-xl border border-cyan-300/15 bg-cyan-300/[0.06] p-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-200/70">
              {actionLabels[activeResult.action]} · {activeResult.provider} / {activeResult.model}
            </p>
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="rounded-md px-2 py-1 text-[10px] text-slate-400 hover:bg-white/10 hover:text-white"
                onClick={() => void copyResult()}
              >
                {copied ? "已复制" : "复制"}
              </button>
              <button
                type="button"
                className="rounded-md px-2 py-1 text-[10px] text-slate-500 hover:bg-white/10 hover:text-white"
                onClick={() => setResultState(null)}
              >
                收起
              </button>
            </div>
          </div>
          <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-200">
            {activeResult.output_text}
          </p>
        </div>
      )}

      {(actionMutation.isPending || noteMutation.isPending) && (
        <div className="mb-2 flex items-center gap-2 text-[11px] text-slate-400">
          <span className="h-3 w-3 animate-spin rounded-full border border-slate-600 border-t-slate-300" />
          {noteMutation.isPending ? "正在保存笔记…" : "AI 正在处理…"}
        </div>
      )}

      {activeFeedback && !actionMutation.isPending && !noteMutation.isPending && (
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
            disabled={!aiAvailable || actionMutation.isPending || noteMutation.isPending}
            className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[11px] font-medium text-slate-300 transition hover:border-cyan-300/30 hover:bg-cyan-300/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
            onClick={() => actionMutation.mutate(actionVariables(action.key))}
          >
            {action.label}
          </button>
        ))}
        <button
          type="button"
          title="加入研究笔记"
          disabled={noteMutation.isPending || actionMutation.isPending}
          className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[11px] font-medium text-slate-300 transition hover:border-emerald-300/30 hover:bg-emerald-300/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
          onClick={() => noteMutation.mutate(noteVariables())}
        >
          笔记
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
