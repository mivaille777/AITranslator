import { describe, expect, it } from "vitest"

import type { AgentActivityItem } from "../state/agent-workspace-state"
import { deriveAgentTimelineStages, getAgentTimelineEventLabel } from "./agent-timeline"

function activity(
  sequence: number,
  eventType: AgentActivityItem["eventType"],
  tone: AgentActivityItem["tone"] = "neutral",
): AgentActivityItem {
  return {
    sequence,
    eventType,
    label: eventType,
    detail: `${eventType} detail`,
    tone,
  }
}

describe("Stage 9.3 Agent timeline", () => {
  it("projects a completed run into Plan, Tool Call, Observation, and Result", () => {
    const stages = deriveAgentTimelineStages([
      activity(0, "agent_start"),
      activity(1, "context_ready", "success"),
      activity(2, "plan_ready"),
      activity(3, "tool_call"),
      activity(4, "tool_result", "success"),
      activity(5, "synthesis_ready", "success"),
      activity(6, "agent_end", "success"),
    ], false)

    expect(stages.map((stage) => stage.id)).toEqual([
      "plan",
      "tool",
      "observation",
      "result",
    ])
    expect(stages.map((stage) => stage.status)).toEqual([
      "complete",
      "complete",
      "complete",
      "complete",
    ])
  })

  it("marks the latest runtime stage active while a run is still streaming", () => {
    const stages = deriveAgentTimelineStages([
      activity(0, "agent_start"),
      activity(1, "context_ready", "success"),
      activity(2, "plan_ready"),
      activity(3, "tool_call"),
    ], true)

    expect(stages.find((stage) => stage.id === "plan")?.status).toBe("complete")
    expect(stages.find((stage) => stage.id === "tool")?.status).toBe("active")
    expect(stages.find((stage) => stage.id === "observation")?.status).toBe("idle")
  })

  it("keeps retries visible as a warning instead of hiding them behind later progress", () => {
    const stages = deriveAgentTimelineStages([
      activity(0, "plan_ready"),
      activity(1, "tool_call"),
      activity(2, "retry", "warning"),
      activity(3, "tool_result", "success"),
    ], true)

    expect(stages.find((stage) => stage.id === "tool")?.status).toBe("warning")
    expect(stages.find((stage) => stage.id === "observation")?.status).toBe("active")
  })

  it("shows planning as active while setup is complete but no plan event has arrived", () => {
    const stages = deriveAgentTimelineStages([
      activity(0, "agent_start"),
      activity(1, "context_ready", "success"),
    ], true)

    expect(stages[0].status).toBe("active")
  })

  it("uses product-facing labels for setup and observation events", () => {
    expect(getAgentTimelineEventLabel("context_ready")).toBe("Setup")
    expect(getAgentTimelineEventLabel("tool_result")).toBe("Observation")
    expect(getAgentTimelineEventLabel("synthesis_ready")).toBe("Result")
  })
})
