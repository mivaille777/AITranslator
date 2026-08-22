import type { AgentRunTraceResponse, AgentTraceEvent, AgentTraceEventType } from "../../api/agent"

export type AgentWorkspacePhase =
  | "idle"
  | "running"
  | "completed"
  | "confirmation_required"
  | "error"

export type AgentActivityTone = "neutral" | "success" | "warning"

export interface AgentActivityItem {
  sequence: number
  eventType: AgentTraceEventType
  label: string
  detail: string
  tone: AgentActivityTone
}

export interface AgentWorkspaceViewState {
  phase: AgentWorkspacePhase
  uiMode: string
  outputText: string
  provider: string
  model: string
  confirmationTool: string
  activities: AgentActivityItem[]
  errorMessage: string
}

function text(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function eventToActivity(event: AgentTraceEvent): AgentActivityItem {
  const payload = event.payload
  switch (event.event_type) {
    case "agent_start":
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: "Agent started",
        detail: text(payload.session_id) || "Preparing this run.",
        tone: "neutral",
      }
    case "context_ready":
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: "Context ready",
        detail: text(payload.resource_title) || text(payload.section_heading) || "Reading context attached.",
        tone: "success",
      }
    case "tool_call": {
      const toolName = text(payload.name) || "tool"
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: `Calling ${toolName}`,
        detail: "Executing a bounded Agent tool.",
        tone: "neutral",
      }
    }
    case "tool_result": {
      const toolName = text(payload.tool_name) || "Tool"
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: `${toolName} completed`,
        detail: text(payload.provider) || "Tool result returned to the Agent.",
        tone: "success",
      }
    }
    case "agent_end": {
      const status = text(payload.status)
      const needsConfirmation = status === "confirmation_required"
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: needsConfirmation ? "Confirmation required" : "Agent completed",
        detail: text(payload.intent) || text(payload.ui_mode) || "Run finished.",
        tone: needsConfirmation ? "warning" : "success",
      }
    }
  }
}

export function deriveAgentWorkspaceState({
  trace,
  pending = false,
  errorMessage = "",
}: {
  trace: AgentRunTraceResponse | null
  pending?: boolean
  errorMessage?: string
}): AgentWorkspaceViewState {
  if (errorMessage) {
    return {
      phase: "error",
      uiMode: trace?.ui_mode ?? "assistant",
      outputText: trace?.run.output_text ?? "",
      provider: trace?.run.provider ?? "",
      model: trace?.run.model ?? "",
      confirmationTool: "",
      activities: trace?.events.map(eventToActivity) ?? [],
      errorMessage,
    }
  }

  if (pending) {
    return {
      phase: "running",
      uiMode: trace?.ui_mode ?? "assistant",
      outputText: trace?.run.output_text ?? "",
      provider: trace?.run.provider ?? "",
      model: trace?.run.model ?? "",
      confirmationTool: "",
      activities: trace?.events.map(eventToActivity) ?? [],
      errorMessage: "",
    }
  }

  if (!trace) {
    return {
      phase: "idle",
      uiMode: "assistant",
      outputText: "",
      provider: "",
      model: "",
      confirmationTool: "",
      activities: [],
      errorMessage: "",
    }
  }

  const confirmationRequired = trace.run.status === "confirmation_required"
  return {
    phase: confirmationRequired ? "confirmation_required" : "completed",
    uiMode: trace.ui_mode,
    outputText: trace.run.output_text,
    provider: trace.run.provider,
    model: trace.run.model,
    confirmationTool: confirmationRequired ? trace.run.plan.tool_name : "",
    activities: trace.events.map(eventToActivity),
    errorMessage: "",
  }
}
