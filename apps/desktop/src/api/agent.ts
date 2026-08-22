import { apiPost } from "./client"
import type { ReadingContextFields } from "./types"

export type AgentRunStatus = "completed" | "confirmation_required"
export type AgentPlanAction = "answer" | "tool"
export type AgentToolEffect = "read" | "compute" | "write"
export type AgentTraceEventType =
  | "agent_start"
  | "context_ready"
  | "tool_call"
  | "tool_result"
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
  tool_result: AgentToolExecuteResponse | null
}

export interface AgentTraceEvent {
  sequence: number
  event_type: AgentTraceEventType
  timestamp: string
  payload: Record<string, unknown>
}

export interface AgentRunTraceResponse {
  session_id: string
  ui_mode: string
  run: AgentRunResponse
  events: AgentTraceEvent[]
}

export function runAgentTrace(payload: AgentRunRequest): Promise<AgentRunTraceResponse> {
  return apiPost<AgentRunTraceResponse, AgentRunRequest>("/api/agent/run/trace", payload)
}
