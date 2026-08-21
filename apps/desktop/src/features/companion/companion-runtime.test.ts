import { describe, expect, it } from "vitest"

import {
  buildCompanionChatRequest,
  companionHistory,
  type CompanionRuntimeMessage,
} from "./companion-runtime"

function message(
  id: string,
  role: "user" | "assistant",
  content: string,
  status: CompanionRuntimeMessage["status"] = "complete",
): CompanionRuntimeMessage {
  return { id, role, content, status }
}

describe("companion runtime", () => {
  it("keeps only complete recent messages in model history", () => {
    const messages = [
      ...Array.from({ length: 18 }, (_, index) =>
        message(`m-${index}`, index % 2 === 0 ? "user" : "assistant", `message ${index}`),
      ),
      message("streaming", "assistant", "partial", "streaming"),
    ]

    const history = companionHistory(messages)

    expect(history).toHaveLength(16)
    expect(history[0]?.content).toBe("message 2")
    expect(history.at(-1)?.content).toBe("message 17")
  })

  it("builds the same reading-grounded request contract for every surface", () => {
    const request = buildCompanionChatRequest({
      conversationId: "conversation-1",
      sessionId: "session-1",
      userMessage: "  explain this  ",
      contextMode: "reading",
      context: {
        source_text: "source",
        translated_text: "translation",
        source_language: "en",
        target_language: "zh-CN",
        resource_url: "file:///paper.pdf",
        resource_title: "Paper",
        section_heading: "3.4",
        context_before: "before",
        context_after: "after",
        source_kind: "pdf",
      },
      messages: [message("u1", "user", "previous question")],
      requestId: 7,
    })

    expect(request).toMatchObject({
      conversation_id: "conversation-1",
      session_id: "session-1",
      user_message: "explain this",
      context_mode: "reading",
      source_text: "source",
      translated_text: "translation",
      resource_title: "Paper",
      section_heading: "3.4",
      request_id: 7,
    })
    expect(request.history).toEqual([
      { role: "user", content: "previous question" },
    ])
  })
})
