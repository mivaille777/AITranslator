import { useEffect, useId, useMemo, useRef, useState } from "react"

import type {
  AgentRunRequest,
  AgentRunTraceResponse,
  AgentTraceEvent,
} from "../../../api/agent"
import {
  streamAgentRun,
  type AgentStreamHandle,
} from "../../../api/agent-stream"
import type { ReadingContextFields } from "../../../api/types"
import type { TranslationWorkspaceController } from "../../translation/useTranslationWorkspace"
import { deriveAgentDecision } from "../decision/agent-decision"
import { buildAgentRunRequest } from "../runtime/agent-run-request"
import { deriveAgentWorkspaceState } from "../state/agent-workspace-state"

export function useAgentRuntime(workspace: TranslationWorkspaceController) {
  const [prompt, setPrompt] = useState("")
  const [trace, setTrace] = useState<AgentRunTraceResponse | null>(null)
  const [liveEvents, setLiveEvents] = useState<AgentTraceEvent[]>([])
  const [pending, setPending] = useState(false)
  const [cancelRequested, setCancelRequested] = useState(false)
  const [cancelledMessage, setCancelledMessage] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const [fallbackReason, setFallbackReason] = useState("")
  const [observabilityRefresh, setObservabilityRefresh] = useState(0)
  const reactInstanceId = useId()
  const sessionId = `agent-workspace-${reactInstanceId.replace(/[^a-zA-Z0-9_-]/g, "")}`
  const conversationId = useRef("")
  const requestId = useRef(0)
  const lastPayload = useRef<AgentRunRequest | null>(null)
  const streamHandle = useRef<AgentStreamHandle | null>(null)

  useEffect(() => {
    return () => {
      streamHandle.current?.close()
      streamHandle.current = null
    }
  }, [])

  const academic = workspace.academicReadingContext
  const reading = workspace.readingSelection
  const sourceText = (academic?.text || reading?.text || workspace.sourceText).trim()
  const context = useMemo<ReadingContextFields>(
    () => {
      if (academic) {
        return {
          resource_url: academic.resource_url,
          resource_title: academic.resource_title,
          section_heading: academic.section_heading,
          context_before: academic.context_before,
          context_after: academic.context_after,
          source_kind: academic.source_kind,
        }
      }
      return {
        resource_url: reading?.resource_url || workspace.browserPage?.url || "",
        resource_title: reading?.resource_title || workspace.browserPage?.title || "",
        section_heading: reading?.section_heading || workspace.browserPage?.heading || "",
        context_before: reading?.context_before || "",
        context_after: reading?.context_after || "",
        source_kind: reading?.source_kind || (workspace.browserPage ? "browser_dom" : "desktop"),
      }
    },
    [academic, reading, workspace.browserPage],
  )

  const viewState = useMemo(
    () => deriveAgentWorkspaceState({
      trace,
      liveEvents,
      pending,
      cancelRequested,
      cancelledMessage,
      errorMessage,
    }),
    [cancelRequested, cancelledMessage, errorMessage, liveEvents, pending, trace],
  )

  const decision = useMemo(
    () => deriveAgentDecision({
      phase: viewState.phase,
      confirmationTool: viewState.confirmationTool,
      errorMessage: viewState.errorMessage,
      fallbackReason,
      activities: viewState.activities,
    }),
    [fallbackReason, viewState],
  )

  function refreshObservability() {
    setObservabilityRefresh((current) => current + 1)
  }

  function rememberConversation(nextConversationId: string) {
    const normalized = nextConversationId.trim()
    if (!normalized) return
    conversationId.current = normalized
    if (lastPayload.current) {
      lastPayload.current = {
        ...lastPayload.current,
        conversation_id: normalized,
      }
    }
  }

  function execute(payload: AgentRunRequest) {
    streamHandle.current?.close()
    streamHandle.current = null
    setPending(true)
    setCancelRequested(false)
    setCancelledMessage("")
    setErrorMessage("")
    setFallbackReason("")
    setLiveEvents([])

    streamHandle.current = streamAgentRun(payload, {
      onEvent(event) {
        if (event.type === "activity") {
          setLiveEvents((current) => {
            if (current.some((item) => item.sequence === event.event.sequence)) return current
            return [...current, event.event].sort((left, right) => left.sequence - right.sequence)
          })
          return
        }

        if (event.type === "cancel_requested") {
          setCancelRequested(true)
          return
        }

        if (event.type === "cancelled") {
          setCancelledMessage(event.message || "Agent run cancelled.")
          setFallbackReason("")
          setCancelRequested(false)
          setPending(false)
          streamHandle.current = null
          refreshObservability()
          return
        }

        if (event.type === "done") {
          rememberConversation(event.trace.run.conversation_id || "")
          setTrace(event.trace)
          setLiveEvents(event.trace.events)
          setFallbackReason("")
          setCancelRequested(false)
          setPending(false)
          streamHandle.current = null
          refreshObservability()
          return
        }

        if (event.type === "error") {
          setErrorMessage(event.message || "Agent run failed.")
          setFallbackReason(event.fallback_reason || "")
          setCancelRequested(false)
          setPending(false)
          streamHandle.current = null
          refreshObservability()
        }
      },
      onTransportError(error) {
        setErrorMessage(error.message || "Agent stream failed.")
        setFallbackReason("")
        setCancelRequested(false)
        setPending(false)
        streamHandle.current = null
      },
    })
  }

  function submitPrompt() {
    const userMessage = prompt.trim()
    if (!userMessage || pending) return
    if (!sourceText) {
      setFallbackReason("")
      setErrorMessage("Capture a reading selection or choose an academic section before running the Agent.")
      return
    }

    requestId.current += 1
    const payload = buildAgentRunRequest({
      context,
      sessionId,
      traceId: `trace-${sessionId}-${requestId.current}-${Date.now().toString(36)}`,
      requestId: requestId.current,
      userMessage,
      sourceText,
      translatedText: workspace.translation?.translated_text || "",
      sourceLanguage: workspace.sourceLanguage,
      targetLanguage: workspace.targetLanguage,
      conversationId: conversationId.current,
      knowledgeDocumentIds: workspace.researchRetrievalScope.knowledgeDocumentIds,
      researchSourceIds: workspace.researchRetrievalScope.researchSourceIds,
    })
    lastPayload.current = payload
    execute(payload)
  }

  function confirmWriteTool() {
    const toolName = viewState.confirmationTool
    const previous = lastPayload.current
    if (!toolName || !previous || pending) return

    requestId.current += 1
    const payload: AgentRunRequest = {
      ...previous,
      conversation_id: conversationId.current || previous.conversation_id,
      confirmed_write_tools: [toolName],
      request_id: requestId.current,
    }
    lastPayload.current = payload
    execute(payload)
  }

  function cancelRun() {
    if (!pending || cancelRequested) return
    setCancelRequested(true)
    streamHandle.current?.cancel()
  }

  return {
    prompt,
    setPrompt,
    sourceText,
    context,
    viewState,
    decision,
    pending,
    cancelRequested,
    observabilityRefresh,
    submitPrompt,
    confirmWriteTool,
    cancelRun,
  }
}
