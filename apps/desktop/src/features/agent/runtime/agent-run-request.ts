import type { AgentRunRequest } from "../../../api/agent"
import type { ReadingContextFields } from "../../../api/types"

export interface BuildAgentRunRequestInput {
  context: ReadingContextFields
  sessionId: string
  traceId: string
  requestId: number
  userMessage: string
  sourceText: string
  translatedText: string
  sourceLanguage: string
  targetLanguage: string
  conversationId: string
  confirmedWriteTools?: string[]
}

export function buildAgentRunRequest({
  context,
  sessionId,
  traceId,
  requestId,
  userMessage,
  sourceText,
  translatedText,
  sourceLanguage,
  targetLanguage,
  conversationId,
  confirmedWriteTools = [],
}: BuildAgentRunRequestInput): AgentRunRequest {
  return {
    ...context,
    session_id: sessionId,
    client_id: sessionId,
    client_surface: "main",
    trace_id: traceId,
    user_message: userMessage,
    source_text: sourceText,
    translated_text: translatedText,
    source_language: sourceLanguage,
    target_language: targetLanguage,
    style: "academic",
    conversation_id: conversationId,
    confirmed_write_tools: confirmedWriteTools,
    request_id: requestId,
  }
}
