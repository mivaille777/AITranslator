import { useCallback, useEffect, useRef, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import { getCompanionChatStatus } from "../../api/companion"
import {
  streamCompanionChat,
  type CompanionChatStreamHandle,
} from "../../api/companion-stream"
import {
  getConversation,
  rewindConversation,
  updateConversationContext,
} from "../../api/conversations"
import type {
  ChatContextMode,
  CompanionChatStreamEvent,
  ConversationContextUpdate,
  ConversationDetail,
} from "../../api/types"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"
import {
  buildCompanionChatRequest,
  companionContextSnapshot,
  createCompanionScope,
  EMPTY_COMPANION_CONTEXT,
  restoreCompanionMessages,
  type CompanionContextSnapshot,
  type CompanionRuntimeMessage,
} from "./companion-runtime"

type StreamEventContext = {
  scopeId: string
  requestId: number
  localUserId: string
  localAssistantId: string
}

export interface CompanionRuntimeResetOptions {
  context?: CompanionContextSnapshot | null
  contextMode?: ChatContextMode
  draft?: string
  sessionId?: string
  scopeId?: string
}

export interface UseCompanionConversationRuntimeOptions {
  initialContext?: CompanionContextSnapshot | null
  initialContextMode?: ChatContextMode
  initialDraft?: string
  initialSessionId?: string
  initialScopeId?: string
  onConversationAccepted?: (conversationId: string) => void
}

export interface CompanionConversationRuntime {
  messages: CompanionRuntimeMessage[]
  draft: string
  setDraft: (value: string) => void
  errorMessage: string
  clearError: () => void
  activeRequestId: number | null
  conversationId: string
  context: CompanionContextSnapshot
  contextMode: ChatContextMode
  chatAvailable: boolean
  chatStatusDetail: string
  chatStatusLoaded: boolean
  openingConversation: boolean
  contextUpdating: boolean
  reset: (options?: CompanionRuntimeResetOptions) => void
  openConversation: (conversationId: string) => Promise<ConversationDetail | null>
  sendMessage: (message?: string, baseMessages?: CompanionRuntimeMessage[]) => boolean
  cancelStream: () => void
  closeActiveStream: () => void
  attachReadingContext: (context: CompanionContextSnapshot) => Promise<void>
  attachSavedContext: () => Promise<void>
  detachReadingContext: () => Promise<void>
  rewriteFromUser: (
    userMessage: CompanionRuntimeMessage,
    replacementText: string,
  ) => Promise<boolean>
}

export function useCompanionConversationRuntime(
  options: UseCompanionConversationRuntimeOptions = {},
): CompanionConversationRuntime {
  const queryClient = useQueryClient()
  const [messages, setMessages] = useState<CompanionRuntimeMessage[]>([])
  const [draft, setDraft] = useState(options.initialDraft ?? "")
  const [errorMessage, setErrorMessage] = useState("")
  const [activeRequestId, setActiveRequestId] = useState<number | null>(null)
  const [conversationId, setConversationId] = useState("")
  const [context, setContext] = useState<CompanionContextSnapshot>(
    options.initialContext ?? EMPTY_COMPANION_CONTEXT,
  )
  const [contextMode, setContextMode] = useState<ChatContextMode>(
    options.initialContextMode ?? "general",
  )
  const [openingConversation, setOpeningConversation] = useState(false)
  const [contextUpdating, setContextUpdating] = useState(false)

  const contextRef = useRef(context)
  const contextModeRef = useRef(contextMode)
  const conversationIdRef = useRef("")
  const sessionIdRef = useRef(
    options.initialSessionId ?? createCompanionScope("session"),
  )
  const scopeRef = useRef(
    options.initialScopeId ?? createCompanionScope("companion"),
  )
  const requestCounterRef = useRef(0)
  const activeRequestRef = useRef<number | null>(null)
  const streamHandleRef = useRef<CompanionChatStreamHandle | null>(null)
  const openingConversationRef = useRef(false)
  const onConversationAcceptedRef = useRef(options.onConversationAccepted)

  onConversationAcceptedRef.current = options.onConversationAccepted

  const chatStatusQuery = useQuery({
    queryKey: queryKeys.companion.chatStatus,
    queryFn: getCompanionChatStatus,
    refetchInterval: queryPolling.companionChatStatus,
    retry: 0,
  })

  const applyConversationId = useCallback((next: string) => {
    conversationIdRef.current = next
    setConversationId(next)
  }, [])

  const applyContext = useCallback((next: CompanionContextSnapshot) => {
    contextRef.current = next
    setContext(next)
  }, [])

  const applyContextMode = useCallback((next: ChatContextMode) => {
    contextModeRef.current = next
    setContextMode(next)
  }, [])

  const closeActiveStream = useCallback(() => {
    streamHandleRef.current?.cancel()
    streamHandleRef.current?.close()
    streamHandleRef.current = null
    activeRequestRef.current = null
    setActiveRequestId(null)
  }, [])

  useEffect(
    () => () => {
      streamHandleRef.current?.close()
    },
    [],
  )

  const reset = useCallback((next: CompanionRuntimeResetOptions = {}) => {
    closeActiveStream()
    applyConversationId("")
    applyContext(next.context ?? EMPTY_COMPANION_CONTEXT)
    applyContextMode(next.contextMode ?? "general")
    sessionIdRef.current = next.sessionId ?? createCompanionScope("session")
    scopeRef.current = next.scopeId ?? createCompanionScope("companion")
    setMessages([])
    setDraft(next.draft ?? "")
    setErrorMessage("")
  }, [applyContext, applyContextMode, applyConversationId, closeActiveStream])

  const applyConversation = useCallback((conversation: ConversationDetail) => {
    applyConversationId(conversation.conversation_id)
    applyContext(companionContextSnapshot(conversation))
    applyContextMode(conversation.context_mode)
    sessionIdRef.current = conversation.session_id
    scopeRef.current = `stored:${conversation.conversation_id}`
    setMessages(restoreCompanionMessages(conversation.messages))
    setDraft("")
    queryClient.setQueryData(
      queryKeys.conversations.detail(conversation.conversation_id),
      conversation,
    )
  }, [applyContext, applyContextMode, applyConversationId, queryClient])

  const openConversation = useCallback(async (nextConversationId: string) => {
    if (!nextConversationId || openingConversationRef.current) return null
    if (conversationIdRef.current === nextConversationId && messages.length > 0) {
      return queryClient.getQueryData<ConversationDetail>(
        queryKeys.conversations.detail(nextConversationId),
      ) ?? null
    }

    closeActiveStream()
    openingConversationRef.current = true
    setOpeningConversation(true)
    setErrorMessage("")
    try {
      const conversation = await queryClient.fetchQuery({
        queryKey: queryKeys.conversations.detail(nextConversationId),
        queryFn: () => getConversation(nextConversationId),
        staleTime: 0,
      })
      applyConversation(conversation)
      return conversation
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to open conversation.",
      )
      return null
    } finally {
      openingConversationRef.current = false
      setOpeningConversation(false)
    }
  }, [applyConversation, closeActiveStream, messages.length, queryClient])

  const recoverConversation = useCallback(async (
    nextConversationId: string,
    expectedScope: string,
  ) => {
    if (!nextConversationId || scopeRef.current !== expectedScope) return
    try {
      const recovered = await getConversation(nextConversationId)
      if (scopeRef.current !== expectedScope) return
      applyConversation(recovered)
      void queryClient.invalidateQueries({ queryKey: ["conversations"] })
    } catch {
      // Preserve the transport error already displayed to the user.
    }
  }, [applyConversation, queryClient])

  const finishRequest = useCallback((requestId: number) => {
    if (activeRequestRef.current !== requestId) return
    activeRequestRef.current = null
    streamHandleRef.current = null
    setActiveRequestId(null)
    void queryClient.invalidateQueries({ queryKey: ["conversations"] })
  }, [queryClient])

  const handleStreamEvent = useCallback((
    event: CompanionChatStreamEvent,
    streamContext: StreamEventContext,
  ) => {
    const { scopeId, requestId, localUserId, localAssistantId } = streamContext
    if (scopeRef.current !== scopeId) return
    if (activeRequestRef.current !== requestId || event.request_id !== requestId) return

    if (event.type === "accepted") {
      const isNewConversation = conversationIdRef.current !== event.conversation_id
      applyConversationId(event.conversation_id)
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
      if (isNewConversation) {
        onConversationAcceptedRef.current?.(event.conversation_id)
      }
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
  }, [applyConversationId, finishRequest, queryClient])

  const sendMessage = useCallback((
    message = draft,
    baseMessages = messages,
  ) => {
    if (activeRequestRef.current !== null) return false

    const normalized = message.trim()
    if (!normalized) return false

    const currentContext = contextRef.current
    if (contextModeRef.current === "reading" && !currentContext.source_text.trim()) {
      setErrorMessage("Reading-grounded Chat requires an attached selection.")
      return false
    }

    const requestId = requestCounterRef.current + 1
    requestCounterRef.current = requestId
    activeRequestRef.current = requestId
    setActiveRequestId(requestId)
    setErrorMessage("")
    setDraft("")

    const localUserId = `user-local-${requestId}`
    const localAssistantId = `assistant-local-${requestId}`
    setMessages([
      ...baseMessages,
      {
        id: localUserId,
        role: "user",
        content: normalized,
        status: "complete",
      },
      {
        id: localAssistantId,
        role: "assistant",
        content: "",
        status: "streaming",
      },
    ])

    if (!sessionIdRef.current) {
      sessionIdRef.current = createCompanionScope("session")
    }
    if (!scopeRef.current) {
      scopeRef.current = createCompanionScope("companion")
    }

    const scopeId = scopeRef.current
    const payload = buildCompanionChatRequest({
      conversationId: conversationIdRef.current,
      sessionId: sessionIdRef.current,
      userMessage: normalized,
      contextMode: contextModeRef.current,
      context: currentContext,
      messages: baseMessages,
      requestId,
    })

    streamHandleRef.current = streamCompanionChat(payload, {
      onEvent: (event) =>
        handleStreamEvent(event, {
          scopeId,
          requestId,
          localUserId,
          localAssistantId,
        }),
      onTransportError: (error) => {
        if (scopeRef.current !== scopeId || activeRequestRef.current !== requestId) return
        setMessages((current) =>
          current.map((runtimeMessage) =>
            runtimeMessage.id === localAssistantId
              ? { ...runtimeMessage, status: "error", errorCode: "transport" }
              : runtimeMessage,
          ),
        )
        setErrorMessage(`${error.message} Recovering persisted stream state…`)
        const persistedConversationId = conversationIdRef.current
        finishRequest(requestId)
        if (persistedConversationId) {
          window.setTimeout(
            () => void recoverConversation(persistedConversationId, scopeId),
            250,
          )
        }
      },
    })
    return true
  }, [draft, finishRequest, handleStreamEvent, messages, recoverConversation])

  const persistContextUpdate = useCallback(async (
    payload: ConversationContextUpdate,
  ) => {
    const currentConversationId = conversationIdRef.current
    if (!currentConversationId) return null
    const updated = await updateConversationContext(currentConversationId, payload)
    applyConversation(updated)
    void queryClient.invalidateQueries({ queryKey: ["conversations"] })
    return updated
  }, [applyConversation, queryClient])

  const attachReadingContext = useCallback(async (
    nextContext: CompanionContextSnapshot,
  ) => {
    if (activeRequestRef.current !== null || contextUpdating) return
    setContextUpdating(true)
    setErrorMessage("")
    try {
      if (conversationIdRef.current) {
        await persistContextUpdate({
          context_mode: "reading",
          source_text: nextContext.source_text,
          translated_text: nextContext.translated_text,
          source_language: nextContext.source_language,
          target_language: nextContext.target_language,
          resource_url: nextContext.resource_url,
          resource_title: nextContext.resource_title,
          section_heading: nextContext.section_heading,
          context_before: nextContext.context_before,
          context_after: nextContext.context_after,
          source_kind: nextContext.source_kind,
        })
      } else {
        applyContext(nextContext)
        applyContextMode("reading")
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to attach reading context.",
      )
    } finally {
      setContextUpdating(false)
    }
  }, [applyContext, applyContextMode, contextUpdating, persistContextUpdate])

  const attachSavedContext = useCallback(async () => {
    if (!contextRef.current.source_text.trim()) return
    await attachReadingContext(contextRef.current)
  }, [attachReadingContext])

  const detachReadingContext = useCallback(async () => {
    if (activeRequestRef.current !== null || contextUpdating) return
    setContextUpdating(true)
    setErrorMessage("")
    try {
      if (conversationIdRef.current) {
        await persistContextUpdate({ context_mode: "general" })
      } else {
        applyContextMode("general")
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to detach reading context.",
      )
    } finally {
      setContextUpdating(false)
    }
  }, [applyContextMode, contextUpdating, persistContextUpdate])

  const rewriteFromUser = useCallback(async (
    userMessage: CompanionRuntimeMessage,
    replacementText: string,
  ) => {
    const currentConversationId = conversationIdRef.current
    const userMessageId = userMessage.serverMessageId || userMessage.id
    if (
      !currentConversationId ||
      !userMessageId ||
      userMessageId.startsWith("user-local-") ||
      activeRequestRef.current !== null
    ) {
      return false
    }

    const normalized = replacementText.trim()
    if (!normalized) return false

    closeActiveStream()
    setErrorMessage("")
    try {
      const rewound = await rewindConversation(currentConversationId, userMessageId)
      applyConversation(rewound)
      const baseMessages = restoreCompanionMessages(rewound.messages)
      return sendMessage(normalized, baseMessages)
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to rewrite conversation branch.",
      )
      return false
    }
  }, [applyConversation, closeActiveStream, sendMessage])

  return {
    messages,
    draft,
    setDraft,
    errorMessage,
    clearError: () => setErrorMessage(""),
    activeRequestId,
    conversationId,
    context,
    contextMode,
    chatAvailable: chatStatusQuery.data?.available ?? false,
    chatStatusDetail: chatStatusQuery.data?.detail ?? "",
    chatStatusLoaded: chatStatusQuery.isSuccess,
    openingConversation,
    contextUpdating,
    reset,
    openConversation,
    sendMessage,
    cancelStream: () => streamHandleRef.current?.cancel(),
    closeActiveStream,
    attachReadingContext,
    attachSavedContext,
    detachReadingContext,
    rewriteFromUser,
  }
}
