import { apiGet, apiPost } from "./client"
import type {
  TranslationRequest,
  TranslationResponse,
  TranslationStatusResponse,
} from "./types"

export type TranslationProviderName = "google_web" | "youdao_web"
export type TranslationProviderMode = "auto" | "youdao_web" | "google_web" | "ai"
export type TranslationCascadeAttempt = {
  provider: "youdao_web" | "google_web" | "ai" | string
  status: "success" | "unavailable"
}
export type TranslationCascadeResponse = TranslationResponse & {
  model: string
  fallback_level: 0 | 1 | 2
  notice: string
  attempts: TranslationCascadeAttempt[]
}
export type TranslationInteractiveRequest = TranslationRequest & {
  provider_mode?: TranslationProviderMode
}

export function getTranslationStatus(): Promise<TranslationStatusResponse> {
  return apiGet<TranslationStatusResponse>("/api/translation/status")
}

export function setTranslationProvider(
  provider: TranslationProviderName,
): Promise<TranslationStatusResponse> {
  return apiPost<TranslationStatusResponse, { provider: TranslationProviderName }>(
    "/api/translation/provider",
    { provider },
  )
}

export function translateText(request: TranslationRequest): Promise<TranslationResponse> {
  return apiPost<TranslationResponse, TranslationRequest>("/api/translation", request)
}

export function translateTextWithFallback(
  request: TranslationInteractiveRequest,
): Promise<TranslationCascadeResponse> {
  return apiPost<TranslationCascadeResponse, TranslationInteractiveRequest>(
    "/api/translation/cascade",
    request,
  )
}
