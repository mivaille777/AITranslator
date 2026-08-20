import { apiGet } from "./client"
import type {
  BrowserBridgeStatusResponse,
  BrowserPageEnvelope,
  BrowserSelectionEnvelope,
} from "./types"

export function getBrowserStatus(): Promise<BrowserBridgeStatusResponse> {
  return apiGet<BrowserBridgeStatusResponse>("/api/browser/status")
}

export function getBrowserSelection(): Promise<BrowserSelectionEnvelope> {
  return apiGet<BrowserSelectionEnvelope>("/api/browser/selection")
}

export function getBrowserPage(): Promise<BrowserPageEnvelope> {
  return apiGet<BrowserPageEnvelope>("/api/browser/page")
}
