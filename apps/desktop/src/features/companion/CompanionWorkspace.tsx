import { useCallback, useEffect, useRef, useState, type FormEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import ReactMarkdown from "react-markdown"
import { Link, useSearchParams } from "react-router-dom"

import {
  dismissCompanionHandoff,
  getCompanionChatStatus,
  getCompanionHandoff,
} from "../../api/companion"
import {
  streamCompanionChat,
  type CompanionChatStreamHandle,
} from "../../api/companion-stream"
import { getConversation, rewindConversation } from "../../api/conversations"
import { saveResearchNote } from "../../api/quick-actions"
import type {
  CompanionChatMessage,
  CompanionChatRequest,
  CompanionChatStreamEvent,
  CompanionHandoff,
  ConversationDetail,
  ConversationMessage,
  ResearchNoteSaveRequest,
} from "../../api/types"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"
import { Badge } from "../../shared/ui/Badge"
import { Button, buttonClassName } from "../../shared/ui/Button"
import { EmptyState } from "../../shared/ui/EmptyState"
import ConversationHistoryPanel from "./ConversationHistoryPanel"

type MessageStatus = "complete" | "streaming" | "cancelled" | "error"
type ContextMode = "none" | "handoff" | "stored" | "draft"

interface WorkspaceMessage extends CompanionChatMessage {
  id: string
  status: MessageStatus
  provider?: string
  model?: string
  serverMessageId?: string
  errorCode?: string
}

interface StreamEventContext {
  scopeId: string
  requestId: number
  localUserId: string
  localAssistantId: string
}

type ActiveContext = CompanionHandoff | ConversationDetail

function historyFrom(messages: WorkspaceMessage[]): CompanionChatMessage[] {
  return messages
    .filter((message) => message.status === "complete" && message.content.trim())
    .slice(-16)
    .map(({ role, content }) => ({ role, content }))
}

function restoredMessages(messages: ConversationMessage[]): WorkspaceMessage[] {
  return messages.map((message) => ({
    id: message.message_id,
    role: message.role,
    content: message.content,
    status: message.status,
    provider: message.provider,
    model: message.model,
    serverMessageId: message.message_id,
    errorCode: message.error_code,
  }))
}

function previousUserMessage(messages: WorkspaceMessage[], assistantIndex: number): WorkspaceMessage | null {
  for (let index = assistantIndex - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "user") return messages[index]
  }
  return null
}

function uniqueScope(prefix: string): string {
  return `${prefix}:${Date.now()}:${Math.random().toString(36).slice(2, 10)}`
}

export default function CompanionWorkspace() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [messages, setMessages] = useState<WorkspaceMessage[]>([])
  const [draft, setDraft] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const [activeRequestId, setActiveRequestId] = useState<number | null>(null)
  const [activeConversationId, setActiveConversationId] = useState("")
  const [restoredConversation, setRestoredConversation] = useState<ConversationDetail | null>(null)
  const [draftContext, setDraftContext] = useState<ActiveContext | null>(null)
  const [openingConversation, setOpeningConversation] = useState(false)
  const [branchingMessageId, setBranchingMessageId] = useState("")
  const handoffIdRef = useRef("")
  const contextModeRef = useRef<ContextMode>("none")
  const scopeRef = useRef("")
  const sessionIdRef = useRef("")
  const requestCounterRef = useRef(0)
  const activeRequestRef = useRef<number | null>(null)
  const conversationIdRef = useRef("")
  const openingConversationRef = useRef(false)
  const streamHandleRef = useRef<CompanionChatStreamHandle | null>(null)

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
  const activeContext: ActiveContext | null = draftContext ?? restoredConversation ?? handoff
  const routedConversationId = searchParams.get("conversation") ?? ""

  const setConversationRoute = useCallback((conversationId: string) => {
    const next = new URLSearchParams(searchParams)
    if (conversationId) next.set("conversation", conversationId)
    else next.delete("conversation")
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const applyConversationId = useCallback((conversationId: string) => {
    conversationIdRef.current = conversationId
    setActiveConversationId(conversationId)
  }, [])

  const closeActiveStream = useCallback(() => {
    streamHandleRef.current?.cancel()
    streamHandleRef.current?.close()
    streamHandleRef.current = null
    activeRequestRef.current = null
    setActiveRequestId(null)
  }, [])

  const resetToHandoff = useCallback((nextHandoff: CompanionHandoff) => {
    closeActiveStream()
    contextModeRef.current = "handoff"
    scopeRef.current = `handoff:${nextHandoff.handoff_id}`
    sessionIdRef.current = `companion-${nextHandoff.handoff_id}`
    setDraftContext(null)
    setRestoredConversation(null)
    applyConversationId("")
    setMessages([])
    setDraft(nextHandoff.suggested_prompt ?? "")
    setErrorMessage("")
    setConversationRoute("")
  }, [applyConversationId, closeActiveStream, setConversationRoute])

  const openConversation = useCallback(async (conversationId: string, updateRoute = true) => {
    if (!conversationId || openingConversationRef.current) return
    if (conversationIdRef.current === conversationId && messages.length > 0) {
      if (updateRoute) setConversationRoute(conversationId)
      return
    }

    closeActiveStream()
    openingConversationRef.current = true
    setOpeningConversation(true)
    setErrorMessage("")
    try {
      const conversation = await queryClient.fetchQuery({
        queryKey: queryKeys.conversations.detail(conversationId),
        queryFn: () => getConversation(conversationId),
        staleTime: 0,
      })
      contextModeRef.current = "stored"
      scopeRef.current = `stored:${conversation.conversation_id}`
      sessionIdRef.current = conversation.session_id
      setDraftContext(null)
      setRestoredConversation(conversation)
      applyConversationId(conversation.conversation_id)
      setMessages(restoredMessages(conversation.messages))
      setDraft("")
      if (updateRoute) setConversationRoute(conversation.conversation_id)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to open conversation.")
    } finally {
      openingConversationRef.current = false
      setOpeningConversation(false)
    }
  }, [applyConversationId, closeActiveStream, messages.length, queryClient, setConversationRoute])

  useEffect(() => {
    const nextId = handoff?.handoff_id ?? ""
    if (nextId === handoffIdRef.current) return

    handoffIdRef.current = nextId
    queueMicrotask(() => {
      if (handoff) {
        resetToHandoff(handoff)
      } else if (contextModeRef.current === "handoff") {
        closeActiveStream()
        contextModeRef.current = "none"
        scopeRef.current = ""
        sessionIdRef.current = ""
        setDraftContext(null)
        setRestoredConversation(null)
        applyConversationId("")
        setMessages([])
        setDraft("")
        setErrorMessage("")
      }
    })
  }, [applyConversationId, closeActiveStream, handoff, resetToHandoff])

  useEffect(() => {
    if (!routedConversationId) return
    if (conversationIdRef.current === routedConversationId) return
    queueMicrotask(() => void openConversation(routedConversationId, false))
  }, [openConversation, routedConversationId])

  useEffect(
    () => () => {
      streamHandleRef.current?.close()
    },
    [],
  )

  const dismissMutation = useMutation({
    mutationFn: (handoffId: string) => dismissCompanionHandoff(handoffId),
    onMutate: closeActiveStream,
    onSuccess: () => {
      contextModeRef.current = "none"
      scopeRef.current = ""
      sessionIdRef.current = ""
      setDraftContext(null)
      setRestoredConversation(null)
      applyConversationId("")
      setMessages([])
      setDraft("")
      setErrorMessage("")
      setConversationRoute("")
      void handoffQuery.refetch()
    },
  })

  const saveNoteMutation = useMutation({
    mutationFn: (payload: ResearchNoteSaveRequest) => saveResearchNote(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["research", "notes"] })
    },
  })

  const recoverConversation = useCallback(async (conversationId: string, expectedScope: string) => {
    if (!conversationId || scopeRef.current !== expectedScope) return
    try {
      const conversation = await getConversation(conversationId)
      if (scopeRef.current !== expectedScope) return
      setMessages(restoredMessages(conversation.messages))
      if (contextModeRef.current === "stored") setRestoredConversation(conversation)
      queryClient.setQueryData(queryKeys.conversations.detail(conversationId), conversation)
      void queryClient.invalidateQueries({ queryKey: ["conversations"] })
    } catch {
      // Keep the transport error already shown to the user.
    }
  }, [queryClient])

  function useCurrentReading() {
    if (!handoff) return
    resetToHandoff(handoff)
  }

  function startNewConversation() {
    if (!activeContext) return
    closeActiveStream()
    contextModeRef.current = "draft"
    scopeRef.current = uniqueScope("draft")
    sessionIdRef.current = uniqueScope("session")
    setDraftContext(activeContext)
    setRestoredConversation(null)
    applyConversationId("")
    setMessages([])
    setDraft("")
    setErrorMessage("")
    setConversationRoute("")
  }

  function handleDeletedActive() {
    if (handoff) {
      resetToHandoff(handoff)
      return
    }
    contextModeRef.current = "none"
    scopeRef.current = ""
    sessionIdRef.current = ""
    setDraftContext(null)
    setRestoredConversation(null)
    applyConversationId("")
    setMessages([])
    setDraft("")
    setErrorMessage("")
    setConversationRoute("")
  }

  function finishRequest(requestId: number) {
    if (activeRequestRef.current !== requestId) return
    activeRequestRef.current = null
    streamHandleRef.current = null
    setActiveRequestId(null)
    void queryClient.invalidateQueries({ queryKey: ["conversations"] })
  }

  function handleStreamEvent(event: CompanionChatStreamEvent, context: StreamEventContext) {
    const { scopeId, requestId, localUserId, localAssistantId } = context
    if (scopeRef.current !== scopeId) return
    if (activeRequestRef.current !== requestId || event.request_id !== requestId) return

    if (event.type === "accepted") {
      applyConversationId(event.conversation_id)
      setConversationRoute(event.conversation_id)
      setMessages((current) =>
        current.map((message) => {
          if (message.id === localUserId && event.user_message_id) {
            return { ...message, serverMessageId: event.user_message_id }
          }
          if (message.id === localAssistantId) {
            return { ...message, serverMessageId: event.message_id }
          }
          return message
        }),
      )
      void queryClient.invalidateQueries({ queryKey: ["conversations"] })
      return
    }

    if (event.type === "delta") {
      setMessages((current) =>
        current.map((message) =>
          message.id === localAssistantId
            ? {
                ...message,
                content: event.accumulated_text,
                serverMessageId: event.message_id,
                status: "streaming",
              }
            : message,
        ),
      )
      return
    }

    if (event.type === "done") {
      setMessages((current) =>
        current.map((message) =>
          message.id === localAssistantId
            ? {
                ...message,
                content: event.output_text,
                serverMessageId: event.message_id,
                provider: event.provider,
                model: event.model,
                status: "complete",
              }
            : message,
        ),
      )
      finishRequest(requestId)
      return
    }

    if (event.type === "cancelled") {
      setMessages((current) =>
        current.map((message) =>
          message.id === localAssistantId
            ? {
                ...message,
                serverMessageId: event.message_id,
                status: "cancelled",
                errorCode: "user_cancelled",
              }
            : message,
        ),
      )
      finishRequest(requestId)
      return
    }

    setMessages((current) =>
      current.map((message) =>
        message.id === localAssistantId
          ? {
              ...message,
              serverMessageId: event.message_id,
              status: "error",
              errorCode: event.code,
            }
          : message,
      ),
    )
    setErrorMessage(event.message || "AI Chat streaming failed.")
    finishRequest(requestId)
  }

  function startExchange(userMessage: string, baseMessages: WorkspaceMessage[] = messages) {
    if (!activeContext || activeRequestRef.current !== null) return
    const normalized = userMessage.trim()
    if (!normalized) return

    const requestId = requestCounterRef.current + 1
    requestCounterRef.current = requestId
    activeRequestRef.current = requestId
    setActiveRequestId(requestId)
    setErrorMessage("")
    setDraft("")

    const localUserId = `user-local-${requestId}`
    const localAssistantId = `assistant-local-${requestId}`
    const history = historyFrom(baseMessages)
    setMessages([
      ...baseMessages,
      { id: localUserId, role: "user", content: normalized, status: "complete" },
      { id: localAssistantId, role: "assistant", content: "", status: "streaming" },
    ])

    const payload: CompanionChatRequest = {
      conversation_id: conversationIdRef.current,
      session_id: sessionIdRef.current || uniqueScope("session"),
      user_message: normalized,
      source_text: activeContext.source_text,
      translated_text: activeContext.translated_text,
      source_language: activeContext.source_language,
      target_language: activeContext.target_language,
      resource_url: activeContext.resource_url,
      resource_title: activeContext.resource_title,
      section_heading: activeContext.section_heading,
      context_before: activeContext.context_before,
      context_after: activeContext.context_after,
      source_kind: activeContext.source_kind,
      history,
      request_id: requestId,
    }

    const scopeId = scopeRef.current
    streamHandleRef.current = streamCompanionChat(payload, {
      onEvent: (streamEvent) =>
        handleStreamEvent(streamEvent, {
          scopeId,
          requestId,
          localUserId,
          localAssistantId,
        }),
      onTransportError: (error) => {
        if (scopeRef.current !== scopeId || activeRequestRef.current !== requestId) return
        setMessages((current) =>
          current.map((message) =>
            message.id === localAssistantId
              ? { ...message, status: "error", errorCode: "transport" }
              : message,
          ),
        )
        setErrorMessage(`${error.message} Recovering persisted stream state…`)
        const conversationId = conversationIdRef.current
        finishRequest(requestId)
        if (conversationId) {
          window.setTimeout(() => void recoverConversation(conversationId, scopeId), 250)
        }
      },
    })
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    startExchange(draft)
  }

  function cancelStream() {
    streamHandleRef.current?.cancel()
  }

  async function rewriteFromUser(userMessage: WorkspaceMessage, replacementText: string) {
    const conversationId = conversationIdRef.current
    const userMessageId = userMessage.serverMessageId || userMessage.id
    if (!conversationId || !userMessageId || userMessageId.startsWith("user-local-")) return
    if (activeRequestRef.current !== null) return

    closeActiveStream()
    setBranchingMessageId(userMessageId)
    setErrorMessage("")
    try {
      const rewound = await rewindConversation(conversationId, userMessageId)
      const baseMessages = restoredMessages(rewound.messages)
      if (contextModeRef.current === "stored") setRestoredConversation(rewound)
      setMessages(baseMessages)
      queryClient.setQueryData(queryKeys.conversations.detail(conversationId), rewound)
      void queryClient.invalidateQueries({ queryKey: ["conversations"] })
      startExchange(replacementText, baseMessages)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to rewrite conversation branch.")
    } finally {
      setBranchingMessageId("")
    }
  }

  function editAndResend(message: WorkspaceMessage) {
    const edited = window.prompt("Edit message and resend", message.content)?.trim()
    if (!edited || edited === message.content) return
    void rewriteFromUser(message, edited)
  }

  function saveLinkedNote() {
    const conversationId = conversationIdRef.current
    if (!activeContext || !conversationId) return
    const lastAssistant = [...messages]
      .reverse()
      .find((message) => message.role === "assistant" && message.status === "complete")
    const handoffAiContent = "ai_content" in activeContext ? activeContext.ai_content : ""
    const handoffAiAction = "ai_action" in activeContext ? activeContext.ai_action : ""
    saveNoteMutation.mutate({
      source_text: activeContext.source_text,
      translated_text: activeContext.translated_text,
      source_language: activeContext.source_language,
      target_language: activeContext.target_language,
      resource_url: activeContext.resource_url,
      resource_title: activeContext.resource_title,
      section_heading: activeContext.section_heading,
      context_before: activeContext.context_before,
      context_after: activeContext.context_after,
      source_kind: activeContext.source_kind,
      ai_content: lastAssistant?.content || handoffAiContent,
      ai_action: lastAssistant ? "conversation_answer" : handoffAiAction,
      conversation_id: conversationId,
    })
  }

  const contextTitle = activeContext
    ? activeContext.resource_title || activeContext.section_heading || "Current selection"
    : "No active context"

  return (
    <section className="grid min-h-[680px] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm xl:grid-cols-[250px_330px_minmax(0,1fr)]">
      <ConversationHistoryPanel
        activeConversationId={activeConversationId}
        hasCurrentReading={Boolean(handoff)}
        canStartNewConversation={Boolean(activeContext)}
        onOpen={(conversationId) => void openConversation(conversationId)}
        onUseCurrentReading={useCurrentReading}
        onNewConversation={startNewConversation}
        onDeletedActive={handleDeletedActive}
      />

      <aside className="border-b border-slate-200 bg-slate-50/70 p-5 xl:border-b-0 xl:border-r">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              {contextModeRef.current === "stored"
                ? "Stored context"
                : contextModeRef.current === "draft"
                  ? "New thread context"
                  : "Frozen context"}
            </p>
            <h2 className="mt-2 truncate text-sm font-semibold text-slate-900">{contextTitle}</h2>
            {activeContext?.section_heading && (
              <p className="mt-1 truncate text-xs text-slate-500">{activeContext.section_heading}</p>
            )}
          </div>
          {contextModeRef.current === "handoff" && handoff && (
            <Button
              size="xs"
              disabled={dismissMutation.isPending}
              onClick={() => dismissMutation.mutate(handoff.handoff_id)}
            >
              Clear
            </Button>
          )}
        </div>

        {activeContext ? (
          <>
            <ContextPreview context={activeContext} />
            {"ai_content" in activeContext && activeContext.ai_content && (
              <div className="mt-3 rounded-xl border border-cyan-100 bg-cyan-50/70 p-3">
                <div className="flex items-center gap-2">
                  <Badge tone="info">Quick Action</Badge>
                  {activeContext.ai_action && (
                    <span className="text-[10px] text-cyan-700/70">{activeContext.ai_action}</span>
                  )}
                </div>
                <p className="mt-2 line-clamp-8 whitespace-pre-wrap text-xs leading-5 text-slate-700">
                  {activeContext.ai_content}
                </p>
              </div>
            )}
            {activeContext.resource_url && (
              <p className="mt-4 break-all font-mono text-[10px] leading-4 text-slate-400">
                {activeContext.resource_url}
              </p>
            )}
            {activeConversationId && (
              <div className="mt-4">
                <Button size="xs" disabled={saveNoteMutation.isPending} onClick={saveLinkedNote}>
                  {saveNoteMutation.isPending ? "Saving…" : "Save linked note"}
                </Button>
                {saveNoteMutation.isSuccess && (
                  <p className="mt-2 text-[10px] text-emerald-600">Research Note linked to this conversation.</p>
                )}
              </div>
            )}
          </>
        ) : (
          <p className="mt-4 text-xs leading-5 text-slate-500">
            Open a saved conversation or create a new AI Chat handoff from the reading overlay.
          </p>
        )}
      </aside>

      <div className="flex min-h-0 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto p-5 lg:p-6">
          {!activeContext && (
            <EmptyState
              title="No active AI Chat context"
              description="Open a saved conversation from the history panel, select text in the browser and choose AI Chat from the overlay, or reopen a Research Note."
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
          )}

          {activeContext && messages.length === 0 && (
            <div className="rounded-2xl bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-500">
              {contextModeRef.current === "stored"
                ? "This conversation was restored from local SQLite. Continue asking questions and new streamed messages will be committed to the same conversation."
                : contextModeRef.current === "draft"
                  ? "This is a fresh thread using the current frozen reading context. SQLite will create the conversation only after the first message is accepted."
                  : "当前划词、译文、网页标题、章节和前后文已经冻结为这次对话上下文。第一次发送后会创建持久化 conversation，回复通过本地 FastAPI WebSocket 增量写入 SQLite。"}
            </div>
          )}

          {activeContext && (
            <div className="mt-4 space-y-3">
              {messages.map((message, index) => {
                const userBefore = message.role === "assistant" ? previousUserMessage(messages, index) : null
                const userServerId = message.role === "user" ? message.serverMessageId || message.id : ""
                const branchBusy = Boolean(branchingMessageId) || activeRequestId !== null
                return (
                  <div
                    key={message.id}
                    className={
                      message.role === "user"
                        ? "ml-auto max-w-[78%] rounded-2xl bg-slate-950 px-4 py-3 text-sm leading-6 text-white"
                        : "max-w-[88%] rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700"
                    }
                  >
                    {message.role === "assistant" ? (
                      <>
                        {message.content ? (
                          <div className="max-w-none"><ReactMarkdown>{message.content}</ReactMarkdown></div>
                        ) : message.status === "streaming" ? (
                          <div className="flex items-center gap-2 text-slate-400">
                            <span className="h-3 w-3 animate-spin rounded-full border border-slate-300 border-t-slate-700" />
                            Waiting for the first token…
                          </div>
                        ) : (
                          <p className="text-slate-400">
                            {message.status === "cancelled" ? "Generation stopped." : "No response content."}
                          </p>
                        )}
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          {message.status === "streaming" && <Badge tone="info">Streaming</Badge>}
                          {message.status === "cancelled" && <Badge tone="warning">Stopped</Badge>}
                          {message.status === "error" && <Badge tone="danger">Failed</Badge>}
                          {message.status === "complete" && message.provider && (
                            <Badge tone="success">
                              {message.provider}{message.model ? ` · ${message.model}` : ""}
                            </Badge>
                          )}
                          {message.errorCode && message.status !== "complete" && (
                            <span className="text-[10px] text-slate-400">{message.errorCode}</span>
                          )}
                          {userBefore && (userBefore.serverMessageId || !userBefore.id.startsWith("user-local-")) && message.status !== "streaming" && (
                            <button
                              type="button"
                              disabled={branchBusy}
                              className="text-[10px] font-medium text-slate-400 hover:text-slate-700 disabled:opacity-40"
                              onClick={() => void rewriteFromUser(userBefore, userBefore.content)}
                            >
                              {message.status === "complete" ? "Regenerate" : "Retry"}
                            </button>
                          )}
                        </div>
                      </>
                    ) : (
                      <>
                        <p className="whitespace-pre-wrap">{message.content}</p>
                        {userServerId && !userServerId.startsWith("user-local-") && (
                          <div className="mt-2 text-right">
                            <button
                              type="button"
                              disabled={branchBusy}
                              className="text-[10px] text-slate-400 hover:text-white disabled:opacity-40"
                              onClick={() => editAndResend(message)}
                            >
                              Edit & resend
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )
              })}

              {errorMessage && (
                <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{errorMessage}</p>
              )}
            </div>
          )}
        </div>

        <form className="border-t border-slate-100 p-4" onSubmit={handleSubmit}>
          {!chatAvailable && chatStatusQuery.isSuccess && (
            <p className="mb-2 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-700">
              AI Chat 未配置：{chatStatusQuery.data.detail}
            </p>
          )}
          <div className="flex items-end gap-2">
            <textarea
              className="max-h-36 min-h-12 flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm leading-6 outline-none transition focus:border-slate-400 focus:bg-white disabled:cursor-not-allowed disabled:opacity-60"
              placeholder={
                activeContext
                  ? activeRequestId === null
                    ? "继续问这段内容…"
                    : "当前回复仍在生成，可先编辑下一条消息…"
                  : "先打开一个 conversation 或当前阅读上下文…"
              }
              value={draft}
              disabled={!activeContext || openingConversation}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
            />
            {activeRequestId !== null ? (
              <Button type="button" variant="danger" size="md" onClick={cancelStream}>
                停止
              </Button>
            ) : (
              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={!activeContext || !chatAvailable || !draft.trim() || openingConversation || Boolean(branchingMessageId)}
              >
                发送
              </Button>
            )}
          </div>
          <p className="mt-2 text-[10px] text-slate-400">
            Enter 发送 · Shift+Enter 换行 · WebSocket Streaming · SQLite branch lifecycle · URL-routed conversation
          </p>
        </form>
      </div>
    </section>
  )
}

function ContextPreview({ context }: { context: ActiveContext }) {
  return (
    <div className="mt-4 space-y-3">
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Selection</p>
        <p className="mt-2 line-clamp-8 text-xs leading-5 text-slate-700">{context.source_text}</p>
      </div>
      {context.translated_text && (
        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Translation</p>
          <p className="mt-2 line-clamp-7 text-xs leading-5 text-slate-600">{context.translated_text}</p>
        </div>
      )}
    </div>
  )
}
