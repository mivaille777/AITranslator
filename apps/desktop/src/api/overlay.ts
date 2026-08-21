import { apiGet, apiPost } from "./client"
import { getCachedReadingSelection } from "./reading"
import type {
  OverlayErrorRequest,
  OverlayLoadingRequest,
  OverlayPresentRequest,
  OverlayStateResponse,
  ReadingContextFields,
} from "./types"
import { desktop } from "../desktop"

const emptyReadingContext: ReadingContextFields = {
  resource_url: "",
  resource_title: "",
  section_heading: "",
  context_before: "",
  context_after: "",
  source_kind: "",
}

function readingContextFor(contextId: string): ReadingContextFields {
  const selection = getCachedReadingSelection()
  if (!selection || selection.selection_id !== contextId) return emptyReadingContext

  return {
    resource_url: selection.resource_url,
    resource_title: selection.resource_title,
    section_heading: selection.section_heading,
    context_before: selection.context_before,
    context_after: selection.context_after,
    source_kind: selection.source_kind,
  }
}

function withReadingContext<T extends { context_id: string }>(payload: T): T & ReadingContextFields {
  return {
    ...readingContextFor(payload.context_id),
    ...payload,
  }
}

async function notifyOverlayStateChanged(contextId = ""): Promise<void> {
  try {
    await desktop.overlay.notifyStateChanged(contextId)
  } catch {
    // Event delivery is an optimization; polling remains the recovery path.
  }
}

export function getOverlayState(): Promise<OverlayStateResponse> {
  return apiGet<OverlayStateResponse>("/api/overlay")
}

export async function showOverlayLoading(payload: OverlayLoadingRequest): Promise<OverlayStateResponse> {
  const response = await apiPost<OverlayStateResponse, OverlayLoadingRequest & ReadingContextFields>(
    "/api/overlay/loading",
    withReadingContext(payload),
  )
  await notifyOverlayStateChanged(payload.context_id)
  return response
}

export async function presentOverlay(payload: OverlayPresentRequest): Promise<OverlayStateResponse> {
  const response = await apiPost<OverlayStateResponse, OverlayPresentRequest & ReadingContextFields>(
    "/api/overlay/present",
    withReadingContext(payload),
  )
  await notifyOverlayStateChanged(payload.context_id)
  return response
}

export async function showOverlayError(payload: OverlayErrorRequest): Promise<OverlayStateResponse> {
  const response = await apiPost<OverlayStateResponse, OverlayErrorRequest & ReadingContextFields>(
    "/api/overlay/error",
    withReadingContext(payload),
  )
  await notifyOverlayStateChanged(payload.context_id)
  return response
}

export async function bindOverlayCompanionConversation(
  contextId: string,
  conversationId: string,
): Promise<OverlayStateResponse> {
  const response = await apiPost<
    OverlayStateResponse,
    { context_id: string; conversation_id: string }
  >(
    "/api/overlay/companion",
    { context_id: contextId, conversation_id: conversationId },
  )
  await notifyOverlayStateChanged(contextId)
  return response
}

export async function dismissOverlay(): Promise<OverlayStateResponse> {
  const response = await apiPost<OverlayStateResponse, Record<string, never>>("/api/overlay/dismiss", {})
  await notifyOverlayStateChanged("")
  return response
}
