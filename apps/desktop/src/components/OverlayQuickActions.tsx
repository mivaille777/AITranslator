import { useCallback, useEffect, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import {
  presentOverlay,
  showOverlayTranslationFailure,
  switchOverlayMode,
} from "../api/overlay"
import {
  getQuickActionStatus,
  runQuickAction,
  saveResearchNote,
} from "../api/quick-actions"
import { translateTextWithFallback } from "../api/translation"
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

export type OverlayCompletedInteraction = "copy" | "handoff"

type OverlayQuickActionsProps = {
  state: OverlayStateResponse
  onPresentationChange?: (presentation: OverlayActionPresentation) => void
  onCompletedInteraction?: (interaction: OverlayCompletedInteraction) => void
}

const explainAction: ActionSpec = {
  key: "reading_explain",
  label: "解释",
  title: "结合上下文解释选中内容",
}

const summarizeAction: ActionSpec = {
  key: "reading_summarize",
  label: "总结",
  title: "总结当前选中的内容",
}

const moreActions: ActionSpec[] = [
  { key: "ai_polish", label: "润色", title: "保持原意和原语言进行 AI 润色" },
  { key: "reading_section_role", label: "段落", title: "分析这段内容在当前章节中的作用" },
]

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
}: OverlayQuickActionsProps) {
  const [resultState, setResultState] = useState<ResultState | null>(null)
  const [feedback, setFeedback] = useState<FeedbackState | null>(null)
  const [moreOpen, setMoreOpen] = useState(false)
  const mode = state.mode ?? "assistant"

  const statusQuery = useQuery({
    queryKey: ["quick-action-status"],
    queryFn: getQuickActionStatus,
    staleTime: 30_000,
    retry: 0,
  })

  const activeResult = resultState?.contextId === state.context_id ? resultState.result : null
  const activeFeedback = feedback?.contextId === state.context_id ? feedback.message : ""
  const aiAvailable = statusQuery.data?.available ?? false

  const setPresentation = useCallback((presentation: OverlayActionPresentation) => {
    onPresentationChange?.(presentation)
  }, [onPresentationChange])

  const actionMutation = useMutation({
    mutationFn: ({ payload }: ActionVariables) => runQuickAction(payload),
    onMutate: ({ contextId }) => {
      if (contextId !== state.context_id) return
      setFeedback(null)
    },
    onSuccess: (result, variables) => {
      if (variables.contextId !== state.context_id) return
      setResultState({ contextId: variables.contextId, result })
      setFeedback({
        contextId: variables.contextId,
        message: `${result.action.replaceAll("_", " ")} completed`,
      })
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

  const modeMutation = useMutation({
    mutationFn: (nextMode: "assistant" | "translation") =>
      switchOverlayMode(state.context_id, nextMode),
    onError: (error) => {
      setFeedback({
        contextId: state.context_id,
        message: error instanceof Error ? error.message : "Unable to switch overlay mode.",
      })
    },
  })

  const translationMutation = useMutation({
    mutationFn: async (targetLanguage: string) => {
      // Keep the overlay interactive while the provider cascade runs. Mode
      // navigation is presentation state; it must not unmount the companion UI.
      await switchOverlayMode(state.context_id, "translation")

      try {
        const result = await translateTextWithFallback({
          source_text: state.source_text,
          source_language: state.source_language,
          target_language: targetLanguage,
        })
        return await presentOverlay({
          context_id: state.context_id,
          source_text: result.source_text,
          translated_text: result.translated_text,
          source_language: result.source_language,
          target_language: result.target_language,
          provider: result.provider === "ai" && result.model
            ? `ai/${result.model}`
            : result.provider,
          translation_notice: result.notice,
          resource_url: state.resource_url,
          resource_title: state.resource_title,
          section_heading: state.section_heading,
          context_before: state.context_before,
          context_after: state.context_after,
          source_kind: state.source_kind,
        })
      } catch (error) {
        await showOverlayTranslationFailure({
          context_id: state.context_id,
          source_text: state.source_text,
          source_language: state.source_language,
          target_language: targetLanguage,
          message: error instanceof Error ? error.message : "Translation failed.",
          resource_url: state.resource_url,
          resource_title: state.resource_title,
          section_heading: state.section_heading,
          context_before: state.context_before,
          context_after: state.context_after,
          source_kind: state.source_kind,
        }).catch(() => undefined)
        throw error
      }
    },
    onError: (error) => {
      setFeedback({
        contextId: state.context_id,
        message: error instanceof Error ? error.message : "Translation failed.",
      })
    },
  })

  const mutateAction = actionMutation.mutate
  const mutateNote = noteMutation.mutate
  const mutateMode = modeMutation.mutate
  const mutateTranslation = translationMutation.mutate

  const runAction = useCallback((action: QuickActionKey) => {
    mutateAction({
      contextId: state.context_id,
      payload: {
        ...baseContext(state),
        action,
        style: "academic",
      },
    })
  }, [mutateAction, state])

  const saveNote = useCallback(() => {
    mutateNote({
      contextId: state.context_id,
      payload: {
        ...baseContext(state),
        ai_content: activeResult?.output_text ?? "",
        ai_action: activeResult?.action ?? "",
      },
    })
  }, [activeResult, mutateNote, state])

  const openAssistant = useCallback(() => {
    setMoreOpen(false)
    setPresentation("compact")
    if (mode !== "assistant") mutateMode("assistant")
  }, [mode, mutateMode, setPresentation])

  const openTranslation = useCallback(() => {
    setMoreOpen(false)
    setPresentation("chat")
    if (state.translated_text.trim()) {
      if (mode !== "translation") mutateMode("translation")
      return
    }
    if (!translationMutation.isPending) mutateTranslation(state.target_language)
  }, [
    mode,
    mutateMode,
    mutateTranslation,
    setPresentation,
    state.target_language,
    state.translated_text,
    translationMutation.isPending,
  ])

  useEffect(() => {
    setPresentation(
      mode === "translation"
        ? (moreOpen ? "expanded" : "chat")
        : (moreOpen ? "expanded" : "compact"),
    )
  }, [mode, moreOpen, setPresentation])

  useEffect(() => {
    const handleModeIntent = (event: Event) => {
      const detail = (event as CustomEvent<{ mode?: string }>).detail
      if (detail?.mode === "assistant") openAssistant()
      if (detail?.mode === "translation") openTranslation()
    }
    window.addEventListener("ait-overlay-mode-intent", handleModeIntent)
    return () => window.removeEventListener("ait-overlay-mode-intent", handleModeIntent)
  }, [openAssistant, openTranslation])

  useEffect(() => subscribeOverlayCommands((command) => {
    if (command === "escape") {
      if (moreOpen) {
        setMoreOpen(false)
        setPresentation(mode === "translation" ? "chat" : "compact")
      } else if (mode === "translation") {
        openAssistant()
      }
      return
    }

    if (command === "more") {
      setMoreOpen((current) => !current)
      return
    }

    if (actionMutation.isPending || noteMutation.isPending || translationMutation.isPending) return
    if (command === "action-1") openTranslation()
    if (command === "action-2" && aiAvailable) runAction(explainAction.key)
    if (command === "action-3" && aiAvailable) runAction(summarizeAction.key)
    if (command === "action-4" && aiAvailable) runAction("ai_polish")
  }), [
    actionMutation.isPending,
    aiAvailable,
    mode,
    moreOpen,
    noteMutation.isPending,
    openAssistant,
    openTranslation,
    runAction,
    setPresentation,
    translationMutation.isPending,
  ])

  if (!state.visible || state.phase === "hidden") return null

  const busy = actionMutation.isPending || noteMutation.isPending || translationMutation.isPending || modeMutation.isPending
  const translationLabel = translationMutation.isPending
    ? "翻译中"
    : state.message && mode === "translation" && !state.translated_text
      ? "重试"
      : "译"

  return (
    <section
      className={`ait-overlay-action-surface relative ${mode === "assistant" ? "is-assistant-primary" : "is-translation-primary"}`}
      data-overlay-mode={mode}
    >
      <div className="ait-overlay-inline-actions flex items-center gap-1.5 border-b border-white/[0.065] px-3 py-2">
        <ActionButton
          active={mode === "translation"}
          disabled={translationMutation.isPending || !state.source_text.trim()}
          label={translationLabel}
          title="翻译当前选区 · 1"
          onClick={openTranslation}
        />
        <ActionButton
          active={activeResult?.action === explainAction.key}
          disabled={!aiAvailable || busy}
          label={explainAction.label}
          title={`${aiAvailable ? explainAction.title : statusQuery.data?.detail || "AI provider is not configured"} · 2`}
          onClick={() => runAction(explainAction.key)}
        />
        <ActionButton
          active={activeResult?.action === summarizeAction.key}
          disabled={!aiAvailable || busy}
          label={summarizeAction.label}
          title={`${aiAvailable ? summarizeAction.title : statusQuery.data?.detail || "AI provider is not configured"} · 3`}
          onClick={() => runAction(summarizeAction.key)}
        />
        <button
          type="button"
          data-tauri-drag-region="false"
          aria-expanded={moreOpen}
          disabled={busy}
          className={`ait-overlay-action-button ml-auto flex h-7 min-w-8 items-center justify-center rounded-full px-2 text-[11px] ${moreOpen ? "is-active" : ""}`}
          title="更多操作 · M"
          onClick={() => setMoreOpen((current) => !current)}
        >
          •••
        </button>
      </div>

      {moreOpen && (
        <div className="flex items-center gap-1.5 border-b border-white/[0.065] px-3 py-2">
          {moreActions.map((action) => (
            <ActionButton
              key={action.key}
              active={activeResult?.action === action.key}
              disabled={!aiAvailable || busy}
              label={action.label}
              title={aiAvailable ? action.title : statusQuery.data?.detail || "AI provider is not configured"}
              onClick={() => runAction(action.key)}
            />
          ))}
          <ActionButton
            disabled={busy}
            label="笔记"
            title="加入研究笔记"
            onClick={saveNote}
          />
        </div>
      )}

      {activeFeedback && !busy && (
        <div className="border-b border-white/[0.055] px-3 py-1.5 text-[9px] text-slate-500">
          {activeFeedback}
        </div>
      )}

      <OverlayCompactChat
        state={state}
        aiResult={activeResult}
        onClose={mode === "translation" ? openAssistant : () => undefined}
      />
    </section>
  )
}

function ActionButton({
  label,
  title,
  active = false,
  disabled = false,
  onClick,
}: {
  label: string
  title: string
  active?: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      data-tauri-drag-region="false"
      title={title}
      disabled={disabled}
      className={`ait-overlay-action-button shrink-0 rounded-full px-3 py-1.5 text-[10px] font-medium ${active ? "is-active" : ""}`}
      onClick={onClick}
    >
      {label}
    </button>
  )
}
