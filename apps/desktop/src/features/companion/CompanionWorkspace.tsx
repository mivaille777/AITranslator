import { useEffect, useRef, useState, type FormEvent } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import ReactMarkdown from "react-markdown"
import { Link } from "react-router-dom"

import {
  dismissCompanionHandoff,
  getCompanionChatStatus,
  getCompanionHandoff,
  sendCompanionChat,
} from "../../api/companion"
import type {
  CompanionChatMessage,
  CompanionChatRequest,
  CompanionHandoff,
} from "../../api/types"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"
import { Badge } from "../../shared/ui/Badge"
import { Button, buttonClassName } from "../../shared/ui/Button"
import { EmptyState } from "../../shared/ui/EmptyState"

type SendVariables = {
  handoffId: string
  userMessage: string
  payload: CompanionChatRequest
}

export default function CompanionWorkspace() {
  const [messages, setMessages] = useState<CompanionChatMessage[]>([])
  const [draft, setDraft] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const handoffIdRef = useRef("")

  const handoffQuery = useQuery({
    queryKey: queryKeys.companion.handoff,
    queryFn: getCompanionHandoff,
    refetchInterval: queryPolling.companionHandoff,
    staleTime: 0,
  })

  const chatStatusQuery = useQuery({
    queryKey: queryKeys.companion.chatStatus,
    queryFn: getCompanionChatStatus,
    refetchInterval: queryPolling.companionChatStatus,
    retry: 0,
  })

  const handoff = handoffQuery.data?.handoff ?? null
  const chatAvailable = chatStatusQuery.data?.available ?? false

  useEffect(() => {
    const nextId = handoff?.handoff_id ?? ""
    if (nextId === handoffIdRef.current) return

    handoffIdRef.current = nextId
    queueMicrotask(() => {
      setMessages([])
      setDraft(handoff?.suggested_prompt ?? "")
      setErrorMessage("")
    })
  }, [handoff])

  const chatMutation = useMutation({
    mutationFn: ({ payload }: SendVariables) => sendCompanionChat(payload),
    onMutate: ({ handoffId, userMessage }) => {
      if (handoffIdRef.current !== handoffId) return
      setErrorMessage("")
      setDraft("")
      setMessages((current) => [...current, { role: "user", content: userMessage }])
    },
    onSuccess: (result, variables) => {
      if (handoffIdRef.current !== variables.handoffId) return
      setMessages((current) => [...current, { role: "assistant", content: result.output_text }])
    },
    onError: (error, variables) => {
      if (handoffIdRef.current !== variables.handoffId) return
      setErrorMessage(error instanceof Error ? error.message : "AI Chat request failed.")
    },
  })

  const dismissMutation = useMutation({
    mutationFn: (handoffId: string) => dismissCompanionHandoff(handoffId),
    onSuccess: () => {
      handoffIdRef.current = ""
      setMessages([])
      setDraft("")
      setErrorMessage("")
      void handoffQuery.refetch()
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!handoff || chatMutation.isPending) return

    const message = draft.trim()
    if (!message) return

    chatMutation.mutate({
      handoffId: handoff.handoff_id,
      userMessage: message,
      payload: {
        session_id: `companion-${handoff.handoff_id}`,
        user_message: message,
        source_text: handoff.source_text,
        translated_text: handoff.translated_text,
        source_language: handoff.source_language,
        target_language: handoff.target_language,
        resource_url: handoff.resource_url,
        resource_title: handoff.resource_title,
        section_heading: handoff.section_heading,
        context_before: handoff.context_before,
        context_after: handoff.context_after,
        source_kind: handoff.source_kind,
        history: messages.slice(-16),
      },
    })
  }

  if (!handoff) {
    return (
      <EmptyState
        title="No active AI Chat context"
        description="Select text in the browser and choose AI Chat from the overlay, or reopen a saved Research Note. The selected text, translation, section, URL, and nearby context will be frozen into the conversation handoff."
        actions={(
          <>
            <Link to="/reading" className={buttonClassName()}>
              Reading Context
            </Link>
            <Link to="/research" className={buttonClassName({ variant: "primary" })}>
              Research Notes
            </Link>
          </>
        )}
      />
    )
  }

  return (
    <section className="grid min-h-[650px] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm xl:grid-cols-[360px_minmax(0,1fr)]">
      <aside className="border-b border-slate-200 bg-slate-50/70 p-5 xl:border-b-0 xl:border-r">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Frozen context</p>
            <h2 className="mt-2 truncate text-sm font-semibold text-slate-900">
              {handoff.resource_title || handoff.section_heading || "Current selection"}
            </h2>
            {handoff.section_heading && <p className="mt-1 truncate text-xs text-slate-500">{handoff.section_heading}</p>}
          </div>
          <Button
            size="xs"
            disabled={dismissMutation.isPending}
            onClick={() => dismissMutation.mutate(handoff.handoff_id)}
          >
            Clear
          </Button>
        </div>

        <ContextPreview handoff={handoff} />

        {handoff.ai_content && (
          <div className="mt-3 rounded-xl border border-cyan-100 bg-cyan-50/70 p-3">
            <div className="flex items-center gap-2">
              <Badge tone="info">Quick Action</Badge>
              {handoff.ai_action && <span className="text-[10px] text-cyan-700/70">{handoff.ai_action}</span>}
            </div>
            <p className="mt-2 line-clamp-8 whitespace-pre-wrap text-xs leading-5 text-slate-700">{handoff.ai_content}</p>
          </div>
        )}

        {handoff.resource_url && (
          <p className="mt-4 break-all font-mono text-[10px] leading-4 text-slate-400">{handoff.resource_url}</p>
        )}
      </aside>

      <div className="flex min-h-0 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto p-5 lg:p-6">
          {messages.length === 0 && (
            <div className="rounded-2xl bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-500">
              当前划词、译文、网页标题、章节和前后文已经冻结为这次对话上下文。当前阶段仍使用非流式请求；Streaming 和持久化将在正式 Chat Stage 接入。
            </div>
          )}

          <div className="mt-4 space-y-3">
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={
                  message.role === "user"
                    ? "ml-auto max-w-[78%] rounded-2xl bg-slate-950 px-4 py-3 text-sm leading-6 text-white"
                    : "max-w-[88%] rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700"
                }
              >
                {message.role === "assistant" ? (
                  <div className="max-w-none"><ReactMarkdown>{message.content}</ReactMarkdown></div>
                ) : (
                  <p className="whitespace-pre-wrap">{message.content}</p>
                )}
              </div>
            ))}

            {chatMutation.isPending && (
              <div className="flex max-w-[70%] items-center gap-2 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-500">
                <span className="h-3 w-3 animate-spin rounded-full border border-slate-300 border-t-slate-700" />
                AI 正在结合当前上下文回答…
              </div>
            )}

            {errorMessage && <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{errorMessage}</p>}
          </div>
        </div>

        <form className="border-t border-slate-100 p-4" onSubmit={handleSubmit}>
          {!chatAvailable && chatStatusQuery.isSuccess && (
            <p className="mb-2 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-700">
              AI Chat 未配置：{chatStatusQuery.data.detail}
            </p>
          )}
          <div className="flex items-end gap-2">
            <textarea
              className="max-h-36 min-h-12 flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm leading-6 outline-none transition focus:border-slate-400 focus:bg-white"
              placeholder="继续问这段内容…"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
            />
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={!chatAvailable || !draft.trim() || chatMutation.isPending}
            >
              发送
            </Button>
          </div>
          <p className="mt-2 text-[10px] text-slate-400">Enter 发送 · Shift+Enter 换行 · 当前历史仅保存在此 WebView 内</p>
        </form>
      </div>
    </section>
  )
}

function ContextPreview({ handoff }: { handoff: CompanionHandoff }) {
  return (
    <div className="mt-4 space-y-3">
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Selection</p>
        <p className="mt-2 line-clamp-8 text-xs leading-5 text-slate-700">{handoff.source_text}</p>
      </div>
      {handoff.translated_text && (
        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Translation</p>
          <p className="mt-2 line-clamp-7 text-xs leading-5 text-slate-600">{handoff.translated_text}</p>
        </div>
      )}
    </div>
  )
}
