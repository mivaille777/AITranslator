import { describe, expect, it } from "vitest"

import { buildAgentRunRequest } from "./agent-run-request"

const context = {
  resource_url: "https://example.com/paper",
  resource_title: "Control Paper",
  section_heading: "Methods",
  context_before: "before",
  context_after: "after",
  source_kind: "browser_dom",
}

describe("Stage 9.2 Agent run request", () => {
  it("builds the main-surface request from runtime-owned state", () => {
    const request = buildAgentRunRequest({
      context,
      sessionId: "agent-session-1",
      traceId: "trace-1",
      requestId: 4,
      userMessage: "Explain this paragraph",
      sourceText: "source",
      translatedText: "translated",
      sourceLanguage: "en",
      targetLanguage: "zh-CN",
      conversationId: "conversation-1",
    })

    expect(request).toMatchObject({
      ...context,
      session_id: "agent-session-1",
      client_id: "agent-session-1",
      client_surface: "main",
      trace_id: "trace-1",
      request_id: 4,
      style: "academic",
      conversation_id: "conversation-1",
      confirmed_write_tools: [],
    })
  })

  it("carries only the explicitly confirmed write tool into a retry", () => {
    const request = buildAgentRunRequest({
      context,
      sessionId: "agent-session-1",
      traceId: "trace-2",
      requestId: 5,
      userMessage: "Save this note",
      sourceText: "source",
      translatedText: "",
      sourceLanguage: "en",
      targetLanguage: "zh-CN",
      conversationId: "conversation-1",
      confirmedWriteTools: ["save_research_note"],
    })

    expect(request.confirmed_write_tools).toEqual(["save_research_note"])
  })
})
