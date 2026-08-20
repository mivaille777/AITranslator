import { getCachedBrowserSelection } from "./browser"
import { apiGet, apiPost } from "./client"
import type {
  OverlayErrorRequest,
  OverlayLoadingRequest,
  OverlayPresentRequest,
  OverlayStateResponse,
  ReadingContextFields,
} from "./types"

const emptyReadingContext: ReadingContextFields = {
  resource_url: "",
  resource_title: "",
  section_heading: "",
  context_before: "",
  context_after: "",
  source_kind: "browser_selection",
}

function readingContextFor(contextId: string): ReadingContextFields {
  const selection = getCachedBrowserSelection()
  if (!selection || selection.selection_id !== contextId) return emptyReadingContext

  return {
    resource_url: selection.url,
    resource_title: selection.title,
    section_heading: selection.heading,
    context_before: selection.context_before,
    context_after: selection.context_after,
    source_kind: "browser_selection",
  }
}

function withReadingContext<T extends { context_id: string }>(payload: T): T & ReadingContextFields {
  return {
    ...readingContextFor(payload.context_id),
    ...payload,
  }
}

export function getOverlayState(): Promise<OverlayStateResponse> {
  return apiGet<OverlayStateResponse>("/api/overlay")
}

export function showOverlayLoading(payload: OverlayLoadingRequest): Promise<OverlayStateResponse> {
  return apiPost<OverlayStateResponse, OverlayLoadingRequest & ReadingContextFields>(
    "/api/overlay/loading",
    withReadingContext(payload),
  )
}

export function presentOverlay(payload: OverlayPresentRequest): Promise<OverlayStateResponse> {
  return apiPost<OverlayStateResponse, OverlayPresentRequest & ReadingContextFields>(
    "/api/overlay/present",
    withReadingContext(payload),
  )
}

export function showOverlayError(payload: OverlayErrorRequest): Promise<OverlayStateResponse> {
  return apiPost<OverlayStateResponse, OverlayErrorRequest & ReadingContextFields>(
    "/api/overlay/error",
    withReadingContext(payload),
  )
}

export function dismissOverlay(): Promise<OverlayStateResponse> {
  return apiPost<OverlayStateResponse, Record<string, never>>("/api/overlay/dismiss", {})
}
