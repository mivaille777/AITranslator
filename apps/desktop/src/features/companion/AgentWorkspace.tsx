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
import { AgentTrace } from "./components/AgentTrace"
import { ContextCard } from "./components/ContextCard"

export function AgentWorkspace({ workspace }: { workspace: TranslationWorkspaceController }) {
  const [prompt, setPrompt] = useState("")
  const [trace, setTrace] = useState<AgentRunTraceResponse | null>(null)
  const [liveEvents, setLiveEvents] = useState<AgentTraceEvent[]>([])
  const [pending, setPending] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")
  const sessionId = useRef(`agent-workspace-${Date.now().toString(36)}`)
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
    () => deriveAgentWorkspaceState({ trace, liveEvents, pending, errorMessage }),
    [errorMessage, liveEvents, pending, trace],
  )

  function execute(payload: AgentRunRequest) {
    streamHandle.current?.close()
    streamHandle.current = null
    setPending(true)
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

        if (event.type === "done") {
          setTrace(event.trace)
          setLiveEvents(event.trace.events)
          setPending(false)
          streamHandle.current = null
          return
        }

        if (event.type === "error") {
          setErrorMessage(event.message || "Agent run failed.")
          setPending(false)
          streamHandle.current = null
        }
      },
      onTransportError(error) {
        setErrorMessage(error.message || "Agent stream failed.")
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
      user_message: userMessage,
      source_text: sourceText,
      translated_text: workspace.translation?.translated_text || "",
      source_language: workspace.sourceLanguage,
      target_language: workspace.targetLanguage,
      style: "academic",
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
      confirmed_write_tools: [toolName],
      request_id: requestId.current,
    }
    lastPayload.current = payload
    execute(payload)
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
        <AgentTrace activities={viewState.activities} running={viewState.phase === "running"} />
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

      <AgentInputComposer
        value={prompt}
        onChange={setPrompt}
        onSubmit={submitPrompt}
        disabled={pending}
        busy={pending}
      />
    </div>
  )
}

export default AgentWorkspace
