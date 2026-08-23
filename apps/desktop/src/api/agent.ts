import { apiPost } from "./client"
import type { ReadingContextFields } from "./types"

export type AgentRunStatus = "completed" | "confirmation_required"
export type AgentPlanAction = "answer" | "tool"
export type AgentToolEffect = "read" | "compute" | "write"
export type AgentClientSurface = "main" | "overlay" | "unknown"
export type AgentTraceEventType =
  | "agent_start"
  | "context_ready"
  | "plan_ready"
  | "tool_call"
  | "retry"
  | "tool_result"
  | "synthesis_ready"
  | "failure"
  | "cancelled"
  | "agent_end"

export interface AgentPlan {
  action: AgentPlanAction
  tool_name: string
  user_visible_reason: string
  arguments: Record<string, string>
}

export interface AgentToolExecuteResponse {
  tool_name: string
  output_text: string
  effect: AgentToolEffect
  provider: string
  model: string
  request_id: number
  data: Record<string, unknown>
}

export interface AgentRunRequest extends ReadingContextFields {
  session_id: string
  trace_id?: string
  client_id?: string
  client_surface?: AgentClientSurface
  user_message: string
  source_text: string
  translated_text: string
  source_language: string
  target_language: string
  style?: string
  conversation_id?: string
  confirmed_write_tools?: string[]
  request_id?: number
}

export interface AgentRunResponse {
  status: AgentRunStatus
  plan: AgentPlan
  output_text: string
  provider: string
  model: string
  request_id: number
  conversation_id: string
  tool_result: AgentToolExecuteResponse | null
}

export interface AgentTraceEvent {
  sequence: number
  event_type: AgentTraceEventType
  timestamp: string
  run_id: string
  trace_id: string
  elapsed_ms: number
  payload: Record<string, unknown>
}

export interface AgentRunTraceResponse {
  run_id: string
  trace_id: string
  session_id: string
  ui_mode: string
  total_duration_ms: number
  run: AgentRunResponse
  events: AgentTraceEvent[]
}

export function runAgentTrace(payload: AgentRunRequest): Promise<AgentRunTraceResponse> {
  return apiPost<AgentRunTraceResponse, AgentRunRequest>("/api/agent/run/trace", payload)
}
