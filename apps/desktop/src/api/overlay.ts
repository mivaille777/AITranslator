import { apiGet, apiPost } from "./client"
import type {
  OverlayErrorRequest,
  OverlayLoadingRequest,
  OverlayPresentRequest,
  OverlayStateResponse,
} from "./types"

export function getOverlayState(): Promise<OverlayStateResponse> {
  return apiGet<OverlayStateResponse>("/api/overlay")
}

export function showOverlayLoading(payload: OverlayLoadingRequest): Promise<OverlayStateResponse> {
  return apiPost<OverlayStateResponse, OverlayLoadingRequest>("/api/overlay/loading", payload)
}

export function presentOverlay(payload: OverlayPresentRequest): Promise<OverlayStateResponse> {
  return apiPost<OverlayStateResponse, OverlayPresentRequest>("/api/overlay/present", payload)
}

export function showOverlayError(payload: OverlayErrorRequest): Promise<OverlayStateResponse> {
  return apiPost<OverlayStateResponse, OverlayErrorRequest>("/api/overlay/error", payload)
}

export function dismissOverlay(): Promise<OverlayStateResponse> {
  return apiPost<OverlayStateResponse, Record<string, never>>("/api/overlay/dismiss", {})
}
