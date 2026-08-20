import { useEffect, useRef, useState, type FormEvent } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import ReactMarkdown from "react-markdown"

import {
  createCompanionHandoff,
  dismissCompanionHandoff,
  getCompanionChatStatus,
  getCompanionHandoff,
  sendCompanionChat,
} from "../api/companion"
import { listResearchNotes } from "../api/quick-actions"
import type {
  CompanionChatMessage,
  CompanionChatRequest,
  CompanionHandoff,
  ResearchNoteListItem,
} from "../api/types"

type SendVariables = {
  handoffId: string
  userMessage: string
  payload: CompanionChatRequest
}

export default function CompanionPanel() {
  const [messages, setMessages] = useState<CompanionChatMessage[]>([])
  const [draft, setDraft] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const [notesOpen, setNotesOpen] = useState(false)
  const handoffIdRef = useRef("")

  const handoffQuery = useQuery({
    queryKey: ["companion-handoff"],
    queryFn: getCompanionHandoff,
    refetchInterval: 650,
    staleTime: 0,
    retry: 1,
  })

  const chatStatusQuery = useQuery({
    queryKey: ["companion-chat-status"],
    queryFn: getCompanionChatStatus,
    refetchInterval: 30_000,
    retry: 0,
  })

  const notesQuery = useQuery({
    queryKey: ["research-notes", "recent"],
    queryFn: () => listResearchNotes(5),
    refetchInterval: 3_000,
    retry: 1,
  })

  const handoff = handoffQuery.data?.handoff ?? null
  const chatAvailable = chatStatusQuery.data?.available ?? false

  useEffect(() => {
    const nextId = handoff?.handoff_id ?? ""
    if (nextId === handoffIdRef.current) return

    handoffIdRef.current = nextId
    setMessages([])
    setDraft(handoff?.suggested_prompt ?? "")
    setErrorMessage("")
    if (handoff) setNotesOpen(false)
  }, [handoff])

  const chatMutation = useMutation({
    mutationFn: ({ payload }: SendVariables) => sendCompanionChat(payload),
    onMutate: ({ handoffId, userMessage }) => {
      if (handoffIdRef.current !== handoffId) return
      setErrorMessage("")
      setDraft("")
      setMessages((current) => [
        ...current,
        { role: "user", content: userMessage },
      ])
    },
    onSuccess: (result, variables) => {
      if (handoffIdRef.current !== variables.handoffId) return
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.output_text },
      ])
    },
    onError: (error, variables) => {
      if (handoffIdRef.current !== variables.handoffId) return
      setErrorMessage(
        error instanceof Error ? error.message : "AI Chat request failed.",
      )
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

  const reopenNoteMutation = useMutation({
    mutationFn: (note: ResearchNoteListItem) =>
      createCompanionHandoff({
        source_text: note.source_text,
        translated_text: note.translated_text,
        source_language: "auto",
        target_language: "zh-CN",
        resource_url: note.resource_url,
        resource_title: note.resource_title,
        section_heading: note.section_heading,
        context_before: note.context_before,
        context_after: note.context_after,
        source_kind: note.source_kind || "research_note",
        ai_content: note.ai_content,
        ai_action: note.ai_action,
        suggested_prompt: "",
      }),
    onSuccess: () => {
      setNotesOpen(false)
      void handoffQuery.refetch()
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!handoff || chatMutation.isPending) return

    const message = draft.trim()
    if (!message) return

    const history = messages.slice(-16)
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
        history,
      },
    })
  }

  if (!handoff) {
    return (
      <div className="fixed bottom-5 right-5 z-40 flex flex-col items-end gap-2">
        {notesOpen && (
          <RecentNotesCard
            notes={notesQuery.data?.notes ?? []}
            total={notesQuery.data?.total ?? 0}
            loading={notesQuery.isPending}
            reopening={reopenNoteMutation.isPending}
            onOpen={(note) => reopenNoteMutation.mutate(note)}
            onClose={() => setNotesOpen(false)}
          />
        )}
        <button
          type="button"
          className="rounded-full border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 shadow-lg transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-xl"
          onClick={() => setNotesOpen((value) => !value)}
        >
          Research Notes · {notesQuery.data?.total ?? "—"}
        </button>
      </div>
    )
  }

  return (
    <aside className="fixed bottom-5 right-5 z-40 flex max-h-[82vh] w-[min(430px,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
      <header className="border-b border-slate-100 px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              AI Chat Context
            </p>
            <h2 className="mt-1 truncate text-sm font-semibold text-slate-900">
              {handoff.resource_title || handoff.section_heading || "Current selection"}
            </h2>
            {handoff.section_heading && (
              <p className="mt-1 truncate text-xs text-slate-500">
                {handoff.section_heading}
              </p>
            )}
          </div>
          <button
            type="button"
            aria-label="Close AI Chat context"
            className="rounded-lg px-2 py-1 text-sm text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            onClick={() => dismissMutation.mutate(handoff.handoff_id)}
          >
            ×
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <ContextPreview handoff={handoff} />

        {handoff.ai_content && (
          <section className="mt-3 rounded-xl border border-cyan-100 bg-cyan-50/60 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-700/70">
              Quick Action result{handoff.ai_action ? ` · ${handoff.ai_action}` : ""}
            </p>
            <p className="mt-2 line-clamp-5 whitespace-pre-wrap text-xs leading-5 text-slate-700">
              {handoff.ai_content}
            </p>
          </section>
        )}

        <div className="mt-4 space-y-3">
          {messages.length === 0 && (
            <p className="rounded-xl bg-slate-50 px-3 py-3 text-xs leading-5 text-slate-500">
              当前划词、译文、网页标题、章节和前后文已经冻结为这次对话的参考上下文。这里先提供非流式上下文问答；流式输出和持久化会在后续 Chat Stage 接入。
            </p>
          )}

          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={
                message.role === "user"
                  ? "ml-8 rounded-xl bg-slate-900 px-3 py-2.5 text-xs leading-5 text-white"
                  : "mr-4 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5 text-xs leading-5 text-slate-700"
              }
            >
              {message.role === "assistant" ? (
                <div className="max-w-none">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{message.content}</p>
              )}
            </div>
          ))}

          {chatMutation.isPending && (
            <div className="mr-10 flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2.5 text-xs text-slate-500">
              <span className="h-3 w-3 animate-spin rounded-full border border-slate-300 border-t-slate-700" />
              AI 正在结合当前阅读上下文回答…
            </div>
          )}

          {errorMessage && (
            <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700">
              {errorMessage}
            </p>
          )}
        </div>

        <details className="mt-4 rounded-xl border border-slate-100 bg-slate-50">
          <summary className="cursor-pointer select-none px-3 py-2 text-xs font-medium text-slate-600">
            最近 Research Notes · {notesQuery.data?.total ?? 0}
          </summary>
          <div className="border-t border-slate-100 p-2">
            <RecentNotesList
              notes={notesQuery.data?.notes ?? []}
              loading={notesQuery.isPending}
              reopening={reopenNoteMutation.isPending}
              onOpen={(note) => reopenNoteMutation.mutate(note)}
            />
          </div>
        </details>
      </div>

      <form className="border-t border-slate-100 p-3" onSubmit={handleSubmit}>
        {!chatAvailable && chatStatusQuery.isSuccess && (
          <p className="mb-2 rounded-lg bg-amber-50 px-2.5 py-2 text-[11px] leading-4 text-amber-700">
            AI Chat 未配置：{chatStatusQuery.data.detail}
          </p>
        )}
        <div className="flex items-end gap-2">
          <textarea
            className="max-h-32 min-h-10 flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 outline-none transition focus:border-slate-400 focus:bg-white"
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
          <button
            type="submit"
            disabled={!chatAvailable || !draft.trim() || chatMutation.isPending}
            className="rounded-xl bg-slate-950 px-3.5 py-2.5 text-xs font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            发送
          </button>
        </div>
        <p className="mt-2 text-[10px] text-slate-400">
          Enter 发送 · Shift+Enter 换行 · 当前历史仅保存在此 WebView 内
        </p>
      </form>
    </aside>
  )
}

function ContextPreview({ handoff }: { handoff: CompanionHandoff }) {
  return (
    <section className="rounded-xl border border-slate-100 bg-slate-50 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
        Frozen selection context
      </p>
      <p className="mt-2 line-clamp-4 text-xs leading-5 text-slate-700">
        {handoff.source_text}
      </p>
      {handoff.translated_text && (
        <p className="mt-2 line-clamp-3 border-t border-slate-200 pt-2 text-xs leading-5 text-slate-500">
          {handoff.translated_text}
        </p>
      )}
    </section>
  )
}

function RecentNotesCard({
  notes,
  total,
  loading,
  reopening,
  onOpen,
  onClose,
}: {
  notes: ResearchNoteListItem[]
  total: number
  loading: boolean
  reopening: boolean
  onOpen: (note: ResearchNoteListItem) => void
  onClose: () => void
}) {
  return (
    <section className="w-[min(390px,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
      <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div>
          <p className="text-xs font-semibold text-slate-800">Recent Research Notes</p>
          <p className="mt-0.5 text-[10px] text-slate-400">{total} notes in SQLite</p>
        </div>
        <button
          type="button"
          className="rounded-lg px-2 py-1 text-sm text-slate-400 hover:bg-slate-100"
          onClick={onClose}
        >
          ×
        </button>
      </header>
      <div className="max-h-80 overflow-y-auto p-2">
        <RecentNotesList
          notes={notes}
          loading={loading}
          reopening={reopening}
          onOpen={onOpen}
        />
      </div>
    </section>
  )
}

function RecentNotesList({
  notes,
  loading,
  reopening,
  onOpen,
}: {
  notes: ResearchNoteListItem[]
  loading: boolean
  reopening: boolean
  onOpen: (note: ResearchNoteListItem) => void
}) {
  if (loading) {
    return <p className="px-2 py-3 text-xs text-slate-400">Loading notes…</p>
  }

  if (notes.length === 0) {
    return <p className="px-2 py-3 text-xs text-slate-400">还没有 Research Notes。</p>
  }

  return (
    <div className="space-y-1">
      {notes.map((note) => (
        <button
          key={note.note_id}
          type="button"
          disabled={reopening}
          className="block w-full rounded-xl px-3 py-2.5 text-left transition hover:bg-slate-100 disabled:opacity-50"
          onClick={() => onOpen(note)}
        >
          <p className="truncate text-xs font-medium text-slate-700">
            {note.display_title}
          </p>
          {note.section_heading && (
            <p className="mt-0.5 truncate text-[10px] text-slate-400">
              {note.section_heading}
            </p>
          )}
          <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-500">
            {note.excerpt}
          </p>
        </button>
      ))}
    </div>
  )
}
