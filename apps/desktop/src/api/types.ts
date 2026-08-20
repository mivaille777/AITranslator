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

export interface BrowserBridgeStatusResponse {
  running: boolean
  host: string
  port: number
  endpoint: string
  has_extension_activity: boolean
  last_activity_age_seconds: number | null
  last_title: string
  last_url: string
  last_heading: string
}

export interface BrowserSelection {
  selection_id: string
  text: string
  url: string
  title: string
  heading: string
  context_before: string
  context_after: string
  frame_url: string
  top_level: boolean
  captured_at_ms: number | null
}

export interface BrowserSelectionEnvelope {
  selection: BrowserSelection | null
}

export interface BrowserPage {
  page_id: string
  url: string
  title: string
  heading: string
  frame_url: string
}

export interface BrowserPageEnvelope {
  page: BrowserPage | null
}

export type OverlayPhase = "hidden" | "loading" | "ready" | "error"

export interface OverlayStateResponse {
  revision: number
  visible: boolean
  phase: OverlayPhase
  context_id: string
  source_text: string
  translated_text: string
  source_language: string
  target_language: string
  provider: string
  message: string
}

export interface OverlayLoadingRequest {
  context_id: string
  source_text: string
  source_language: string
  target_language: string
}

export interface OverlayPresentRequest extends OverlayLoadingRequest {
  translated_text: string
  provider: string
}

export interface OverlayErrorRequest {
  context_id: string
  source_text: string
  source_language: string
  target_language: string
  message: string
}
