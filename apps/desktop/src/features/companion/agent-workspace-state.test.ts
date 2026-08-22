import { describe, expect, it } from "vitest"

import type { AgentRunTraceResponse } from "../../api/agent"
import { deriveAgentWorkspaceState } from "./agent-workspace-state"

const trace: AgentRunTraceResponse = {
  session_id: "session-1",
  ui_mode: "translation",
  run: {
    status: "completed",
    plan: {
      action: "tool",
      tool_name: "translate_selection",
      user_visible_reason: "Translate the current selection.",
      arguments: { target_language: "zh-CN" },
    },
    output_text: "贝叶斯优化",
    provider: "fake",
    model: "stub-model",
    request_id: 7,
    tool_result: null,
  },
  events: [
    {
      sequence: 0,
      event_type: "agent_start",
      timestamp: "2026-08-22T00:00:00+00:00",
      payload: { session_id: "session-1" },
    },
    {
      sequence: 1,
      event_type: "context_ready",
      timestamp: "2026-08-22T00:00:01+00:00",
      payload: { resource_title: "Control Paper" },
    },
    {
      sequence: 2,
      event_type: "tool_call",
      timestamp: "2026-08-22T00:00:02+00:00",
      payload: { name: "translate_selection" },
    },
    {
      sequence: 3,
      event_type: "agent_end",
      timestamp: "2026-08-22T00:00:03+00:00",
      payload: { status: "completed", intent: "translate_selection" },
    },
  ],
}

describe("agent workspace state", () => {
  it("projects trace events into stable activity items", () => {
    const state = deriveAgentWorkspaceState({ trace })

    expect(state.phase).toBe("completed")
    expect(state.uiMode).toBe("translation")
    expect(state.outputText).toBe("贝叶斯优化")
    expect(state.activities.map((item) => item.label)).toEqual([
      "Agent started",
      "Context ready",
      "Tool planned: translate_selection",
      "Agent completed",
    ])
  })

  it("surfaces write confirmation as a dedicated workspace phase", () => {
    const state = deriveAgentWorkspaceState({
      trace: {
        ...trace,
        ui_mode: "note",
        run: {
          ...trace.run,
          status: "confirmation_required",
          plan: {
            action: "tool",
            tool_name: "save_research_note",
            user_visible_reason: "Saving changes persistent state.",
            arguments: {},
          },
          output_text: "",
        },
      },
    })

    expect(state.phase).toBe("confirmation_required")
    expect(state.confirmationTool).toBe("save_research_note")
  })

  it("does not discard the previous trace while a new run is pending", () => {
    const state = deriveAgentWorkspaceState({ trace, pending: true })

    expect(state.phase).toBe("running")
    expect(state.activities).toHaveLength(4)
    expect(state.outputText).toBe("贝叶斯优化")
  })
})
