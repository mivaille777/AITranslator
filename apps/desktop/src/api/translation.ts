import { apiGet, apiPost } from "./client"
import type {
  TranslationRequest,
  TranslationResponse,
  TranslationStatusResponse,
} from "./types"

export type TranslationProviderName = "google_web" | "youdao_web"

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
