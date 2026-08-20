import { apiGet, apiPost } from "./client"
import type {
  TranslationRequest,
  TranslationResponse,
  TranslationStatusResponse,
} from "./types"

export function getTranslationStatus(): Promise<TranslationStatusResponse> {
  return apiGet<TranslationStatusResponse>("/api/translation/status")
}

export function translateText(request: TranslationRequest): Promise<TranslationResponse> {
  return apiPost<TranslationResponse, TranslationRequest>("/api/translation", request)
}
