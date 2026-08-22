import { apiGet } from "./client"

export interface AgentModelRouteInfo {
  role: string
  provider: string
  model: string
  thinking_enabled: boolean
}

export interface AgentPromptInfo {
  name: string
  version: string
  prompt_id: string
}

export interface AgentRuntimeConfig {
  model_routes: AgentModelRouteInfo[]
  prompts: AgentPromptInfo[]
  planner_context_max_chars: number
  chat_context_max_chars: number
  document_content_trust: string
  planner_argument_policy: string
  write_confirmation_required: boolean
}

export function getAgentRuntimeConfig(): Promise<AgentRuntimeConfig> {
  return apiGet<AgentRuntimeConfig>("/api/agent/runtime/config")
}
