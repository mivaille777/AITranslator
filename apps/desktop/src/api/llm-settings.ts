import { apiGet, apiPut } from "./client"

export type LlmProviderId = "deepseek" | "openai_compatible"

export interface LlmProviderOption {
  id: LlmProviderId
  label: string
  requires_base_url: boolean
  default_model: string
  default_base_url: string
}

export interface LlmSettings {
  provider: LlmProviderId
  model: string
  base_url: string
  providers: LlmProviderOption[]
}

export interface LlmSettingsUpdate {
  provider: LlmProviderId
  model: string
  base_url: string
}

const LLM_SETTINGS_PATH = "/api/settings/llm"

export function getLlmSettings(): Promise<LlmSettings> {
  return apiGet<LlmSettings>(LLM_SETTINGS_PATH)
}

export function updateLlmSettings(payload: LlmSettingsUpdate): Promise<LlmSettings> {
  return apiPut<LlmSettings, LlmSettingsUpdate>(LLM_SETTINGS_PATH, payload)
}
