import { apiGet } from "./client"
import type {
  BrowserBridgeStatusResponse,
  BrowserPageEnvelope,
  BrowserSelection,
  BrowserSelectionEnvelope,
} from "./types"

let latestBrowserSelection: BrowserSelection | null = null

export function getBrowserStatus(): Promise<BrowserBridgeStatusResponse> {
  return apiGet<BrowserBridgeStatusResponse>("/api/browser/status")
}

export async function getBrowserSelection(): Promise<BrowserSelectionEnvelope> {
  const envelope = await apiGet<BrowserSelectionEnvelope>("/api/browser/selection")
  latestBrowserSelection = envelope.selection
  return envelope
}

export function getCachedBrowserSelection(): BrowserSelection | null {
  return latestBrowserSelection
}

export function getBrowserPage(): Promise<BrowserPageEnvelope> {
  return apiGet<BrowserPageEnvelope>("/api/browser/page")
}
