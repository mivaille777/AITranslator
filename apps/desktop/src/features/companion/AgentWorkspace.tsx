import { useEffect, useMemo, useRef, useState } from "react"

import type {
  AgentRunRequest,
  AgentRunTraceResponse,
  AgentTraceEvent,
} from "../../api/agent"
import {
  streamAgentRun,
  type AgentStreamHandle,
} from "../../api/agent-stream"
import type { TranslationWorkspaceController } from "../translation/useTranslationWorkspace"
import { deriveAgentWorkspaceState } from "./agent-workspace-state"
import { AgentHeader } from "./components/AgentHeader"
import { AgentInputComposer } from "./components/AgentInputComposer"
import { AgentMessage } from "./components/AgentMessage"
import { AgentObservabilityPanel } from "./components/AgentObservabilityPanel"
import { AgentTrace } from "./components/AgentTrace"
import { ContextCard } from "./components/ContextCard"

export function AgentWorkspace({ workspace }: { workspace: TranslationWorkspaceController }) {
  const [prompt, setPrompt] = useState("")
  const [trace, setTrace] = useState<AgentRunTraceResponse | null>(null)
  const [liveEvents, setLiveEvents] = useState<AgentTraceEvent[]>([])
  const [pending, setPending] = useState(false)
  const [cancelRequested, setCancelRequested] = useState(false)
  const [cancelledMessage, setCancelledMessage] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const [observabilityRefresh, setObservabilityRefresh] = useState(0)
  const sessionId = useRef(`agent-workspace-${Date.now().toString(36)}`)
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

  const reading = workspace.readingSelection
  const sourceText = (reading?.text || workspace.sourceText).trim()
  const context = useMemo(
    () => ({
      resource_url: reading?.resource_url || workspace.browserPage?.url || "",
      resource_title: reading?.resource_title || workspace.browserPage?.title || "",
      section_heading: reading?.section_heading || workspace.browserPage?.heading || "",
      context_before: reading?.context_before || "",
      context_after: reading?.context_after || "",
      source_kind: reading?.source_kind || (workspace.browserPage ? "browser_dom" : "desktop"),
    }),
    [reading, workspace.browserPage],
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
          setCancelRequested(false)
          setPending(false)
          streamHandle.current = null
          refreshObservability()
          return
        }

        if (event.type === "error") {
          const fallback = event.fallback_reason ? ` (${event.fallback_reason})` : ""
          setErrorMessage(`${event.message || "Agent run failed."}${fallback}`)
          setCancelRequested(false)
          setPending(false)
          streamHandle.current = null
          refreshObservability()
        }
      },
      onTransportError(error) {
        setErrorMessage(error.message || "Agent stream failed.")
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
      setErrorMessage("Capture a reading selection or enter source text before running the Agent.")
      return
    }

    requestId.current += 1
    const payload: AgentRunRequest = {
      ...context,
      session_id: sessionId.current,
      client_id: sessionId.current,
      client_surface: "main",
      trace_id: `trace-${sessionId.current}-${requestId.current}-${Date.now().toString(36)}`,
      user_message: userMessage,
      source_text: sourceText,
      translated_text: workspace.translation?.translated_text || "",
      source_language: workspace.sourceLanguage,
      target_language: workspace.targetLanguage,
      style: "academic",
      conversation_id: conversationId.current,
      confirmed_write_tools: [],
      request_id: requestId.current,
    }
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

  return (
    <div className="space-y-4">
      <AgentHeader phase={viewState.phase} uiMode={viewState.uiMode} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <ContextCard
          text={sourceText}
          title={context.resource_title}
          section={context.section_heading}
          sourceKind={context.source_kind}
        />
        <AgentTrace
          activities={viewState.activities}
          running={viewState.phase === "running" || viewState.phase === "cancelling"}
          runId={viewState.runId}
          traceId={viewState.traceId}
          totalDurationMs={viewState.totalDurationMs}
        />
      </div>

      <AgentMessage
        content={viewState.outputText}
        phase={viewState.phase}
        provider={viewState.provider}
        model={viewState.model}
        confirmationTool={viewState.confirmationTool}
        errorMessage={viewState.errorMessage}
        onConfirm={confirmWriteTool}
        confirming={pending}
      />

      <AgentObservabilityPanel
        refreshToken={observabilityRefresh}
        currentRunId={viewState.runId}
      />

      <AgentInputComposer
        value={prompt}
        onChange={setPrompt}
        onSubmit={submitPrompt}
        onCancel={cancelRun}
        disabled={pending}
        busy={pending}
        cancelling={cancelRequested}
      />
    </div>
  )
}

export default AgentWorkspace
