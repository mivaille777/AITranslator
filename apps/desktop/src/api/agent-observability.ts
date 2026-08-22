import { apiGet, apiPost } from "./client"

export interface AgentRunMetric {
  run_id: string
  trace_id: string
  session_id: string
  created_at: string
  status: string
  intent: string
  ui_mode: string
  tool_name: string
  provider: string
  model: string
  total_duration_ms: number
  planning_duration_ms: number
  tool_duration_ms: number
  synthesis_duration_ms: number
  retry_count: number
  failure_count: number
  timeout_count: number
  fallback_reason: string
  event_count: number
}

export interface AgentObservabilitySummary {
  sample_size: number
  completed_runs: number
  failed_runs: number
  cancelled_runs: number
  confirmation_required_runs: number
  success_rate: number
  schema_valid_rate: number
  retry_rate: number
  failure_rate: number
  timeout_rate: number
  fallback_rate: number
  average_total_duration_ms: number
  p95_total_duration_ms: number
  average_planning_duration_ms: number
  average_tool_duration_ms: number
  average_synthesis_duration_ms: number
}

export interface AgentEvaluationRequest {
  case_id: string
  expected_intent?: string
  expected_tool_name?: string
  expected_status?: string
  max_total_duration_ms?: number
  max_retry_count?: number
  require_zero_failures?: boolean
}

export interface AgentEvaluationResponse {
  case_id: string
  run_id: string
  trace_id: string
  passed: boolean
  score: number
  intent_match: boolean
  tool_match: boolean
  status_match: boolean
  latency_pass: boolean
  retry_pass: boolean
  failure_pass: boolean
  failures: string[]
}

export async function getAgentObservabilitySummary(limit = 100): Promise<AgentObservabilitySummary> {
  return apiGet<AgentObservabilitySummary>(`/api/agent/observability/summary?limit=${limit}`)
}

export async function getRecentAgentRuns(limit = 8): Promise<AgentRunMetric[]> {
  const response = await apiGet<{ runs: AgentRunMetric[] }>(
    `/api/agent/observability/recent?limit=${limit}`,
  )
  return response.runs
}

export function evaluateAgentRun(
  runId: string,
  request: AgentEvaluationRequest,
): Promise<AgentEvaluationResponse> {
  return apiPost<AgentEvaluationResponse, AgentEvaluationRequest>(
    `/api/agent/evaluation/run/${encodeURIComponent(runId)}`,
    request,
  )
}
