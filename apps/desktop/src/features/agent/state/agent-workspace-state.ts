import type { AgentRunTraceResponse, AgentTraceEvent, AgentTraceEventType } from "../../../api/agent"

export type AgentWorkspacePhase =
  | "idle"
  | "running"
  | "cancelling"
  | "cancelled"
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
  runId: string
  traceId: string
  totalDurationMs: number
  confirmationTool: string
  activities: AgentActivityItem[]
  errorMessage: string
}

function text(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function numeric(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0
}

function withDuration(detail: string, payload: Record<string, unknown>): string {
  const duration = numeric(payload.duration_ms)
  return duration > 0 ? `${detail} · ${duration} ms` : detail
}

function eventToActivity(event: AgentTraceEvent): AgentActivityItem {
  const payload = event.payload
  switch (event.event_type) {
    case "agent_start":
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: "Agent started",
        detail: text(payload.run_id) || text(payload.session_id) || "Preparing this run.",
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
    case "plan_ready": {
      const action = text(payload.action)
      const toolName = text(payload.tool_name)
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: toolName ? `Plan ready: ${toolName}` : "Plan ready",
        detail: withDuration(
          text(payload.user_visible_reason) || (action === "answer" ? "The Agent will answer directly." : "The Agent selected its next action."),
          payload,
        ),
        tone: "neutral",
      }
    }
    case "tool_call": {
      const toolName = text(payload.name) || "tool"
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: `Tool planned: ${toolName}`,
        detail: "The Agent selected a bounded tool. Execution is confirmed by a tool result.",
        tone: "neutral",
      }
    }
    case "retry": {
      const toolName = text(payload.tool_name) || "tool"
      const attempt = numeric(payload.attempt)
      const maxAttempts = numeric(payload.max_attempts)
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: `Retrying ${toolName}`,
        detail: `${attempt > 0 && maxAttempts > 0 ? `Attempt ${attempt}/${maxAttempts}. ` : ""}${text(payload.reason) || "Transient tool failure."}`,
        tone: "warning",
      }
    }
    case "tool_result": {
      const toolName = text(payload.tool_name) || "Tool"
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: `${toolName} completed`,
        detail: withDuration(text(payload.provider) || "Tool result returned to the Agent.", payload),
        tone: "success",
      }
    }
    case "synthesis_ready":
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: "Response synthesized",
        detail: withDuration(text(payload.model) || text(payload.provider) || "Final response generated.", payload),
        tone: "success",
      }
    case "failure":
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: `Failed: ${text(payload.stage) || "runtime"}`,
        detail: `${text(payload.message) || "Agent execution failed."}${text(payload.fallback_reason) ? ` · ${text(payload.fallback_reason)}` : ""}`,
        tone: "warning",
      }
    case "cancelled":
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: "Agent cancelled",
        detail: text(payload.message) || "Cancellation reached a safe checkpoint.",
        tone: "warning",
      }
    case "agent_end": {
      const status = text(payload.status)
      const needsConfirmation = status === "confirmation_required"
      const failed = status === "failed"
      const cancelled = status === "cancelled"
      return {
        sequence: event.sequence,
        eventType: event.event_type,
        label: needsConfirmation ? "Confirmation required" : failed ? "Agent failed" : cancelled ? "Agent cancelled" : "Agent completed",
        detail: withDuration(text(payload.intent) || text(payload.ui_mode) || "Run finished.", {
          duration_ms: payload.total_duration_ms,
        }),
        tone: needsConfirmation || failed || cancelled ? "warning" : "success",
      }
    }
  }
}

function activitySource(
  trace: AgentRunTraceResponse | null,
  liveEvents: AgentTraceEvent[],
): AgentTraceEvent[] {
  if (liveEvents.length > 0) return liveEvents
  return trace?.events ?? []
}

export function deriveAgentWorkspaceState({
  trace,
  liveEvents = [],
  pending = false,
  cancelRequested = false,
  cancelledMessage = "",
  errorMessage = "",
}: {
  trace: AgentRunTraceResponse | null
  liveEvents?: AgentTraceEvent[]
  pending?: boolean
  cancelRequested?: boolean
  cancelledMessage?: string
  errorMessage?: string
}): AgentWorkspaceViewState {
  const activities = activitySource(trace, liveEvents).map(eventToActivity)
  const shared = {
    uiMode: trace?.ui_mode ?? "assistant",
    outputText: trace?.run.output_text ?? "",
    provider: trace?.run.provider ?? "",
    model: trace?.run.model ?? "",
    runId: trace?.run_id ?? liveEvents.at(-1)?.run_id ?? "",
    traceId: trace?.trace_id ?? liveEvents.at(-1)?.trace_id ?? "",
    totalDurationMs: trace?.total_duration_ms ?? liveEvents.at(-1)?.elapsed_ms ?? 0,
    activities,
  }

  if (errorMessage) {
    return {
      ...shared,
      phase: "error",
      confirmationTool: "",
      errorMessage,
    }
  }

  if (cancelledMessage) {
    return {
      ...shared,
      phase: "cancelled",
      confirmationTool: "",
      errorMessage: cancelledMessage,
    }
  }

  if (pending) {
    return {
      ...shared,
      phase: cancelRequested ? "cancelling" : "running",
      confirmationTool: "",
      errorMessage: "",
    }
  }

  if (!trace) {
    return {
      ...shared,
      phase: "idle",
      confirmationTool: "",
      errorMessage: "",
    }
  }

  const confirmationRequired = trace.run.status === "confirmation_required"
  return {
    ...shared,
    phase: confirmationRequired ? "confirmation_required" : "completed",
    confirmationTool: confirmationRequired ? trace.run.plan.tool_name : "",
    errorMessage: "",
  }
}
