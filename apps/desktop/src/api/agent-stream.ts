import { apiWebSocketUrl } from "./client"
import type {
  AgentRunRequest,
  AgentRunTraceResponse,
  AgentTraceEvent,
} from "./agent"

export interface AgentStreamAcceptedEvent {
  type: "accepted"
  request_id: number
  session_id: string
}

export interface AgentStreamActivityEvent {
  type: "activity"
  request_id: number
  session_id: string
  event: AgentTraceEvent
}

export interface AgentStreamDoneEvent {
  type: "done"
  request_id: number
  session_id: string
  trace: AgentRunTraceResponse
}

export interface AgentStreamErrorEvent {
  type: "error"
  request_id: number
  session_id: string
  code: string
  message: string
}

export type AgentStreamEvent =
  | AgentStreamAcceptedEvent
  | AgentStreamActivityEvent
  | AgentStreamDoneEvent
  | AgentStreamErrorEvent

export interface AgentStreamHandlers {
  onEvent: (event: AgentStreamEvent) => void
  onTransportError: (error: Error) => void
}

export interface AgentStreamHandle {
  requestId: number
  close: () => void
}

const terminalTypes = new Set<AgentStreamEvent["type"]>(["done", "error"])

function parseEvent(raw: string): AgentStreamEvent {
  const parsed = JSON.parse(raw) as Partial<AgentStreamEvent>
  if (!parsed || typeof parsed !== "object" || typeof parsed.type !== "string") {
    throw new Error("Invalid Agent stream event.")
  }
  return parsed as AgentStreamEvent
}

export function streamAgentRun(
  payload: AgentRunRequest,
  handlers: AgentStreamHandlers,
): AgentStreamHandle {
  const requestId = payload.request_id ?? 0
  const socket = new WebSocket(apiWebSocketUrl("/api/agent/stream"))
  let terminal = false

  socket.addEventListener("open", () => {
    socket.send(JSON.stringify({ type: "start", request: payload }))
  })

  socket.addEventListener("message", (message) => {
    if (terminal) return
    try {
      const event = parseEvent(String(message.data))
      if (event.request_id !== requestId) return
      handlers.onEvent(event)
      if (terminalTypes.has(event.type)) {
        terminal = true
        socket.close(1000, event.type)
      }
    } catch (error) {
      terminal = true
      handlers.onTransportError(
        error instanceof Error ? error : new Error("Invalid Agent stream event."),
      )
      socket.close(1002, "invalid-agent-stream-event")
    }
  })

  socket.addEventListener("error", () => {
    if (terminal) return
    terminal = true
    handlers.onTransportError(new Error("Unable to connect to the Agent stream."))
  })

  socket.addEventListener("close", (event) => {
    if (terminal) return
    terminal = true
    handlers.onTransportError(
      new Error(`Agent stream closed unexpectedly (${event.code}).`),
    )
  })

  return {
    requestId,
    close() {
      terminal = true
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close(1000, "client-close")
      }
    },
  }
}
