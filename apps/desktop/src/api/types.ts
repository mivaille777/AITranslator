export interface HealthResponse {
  status: "ok"
  service: string
}

export interface TranslationRequest {
  source_text: string
  source_language: string
  target_language: string
  request_id?: number
}

export interface TranslationResponse {
  source_text: string
  translated_text: string
  source_language: string
  target_language: string
  provider: string
  request_id: number
}

export interface TranslationStatusResponse {
  provider: string
  source_language: string
  target_language: string
}
