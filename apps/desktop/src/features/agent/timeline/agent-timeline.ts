import type { AgentTraceEventType } from "../../../api/agent"
import type { AgentActivityItem } from "../state/agent-workspace-state"

export type AgentTimelineStageId = "plan" | "tool" | "observation" | "result"
export type AgentTimelineStageStatus = "idle" | "active" | "complete" | "warning"

export interface AgentTimelineStage {
  id: AgentTimelineStageId
  label: string
  description: string
  status: AgentTimelineStageStatus
  activityCount: number
}

export const agentTimelineStageDefinitions = [
  {
    id: "plan",
    label: "Plan",
    description: "Choose the next bounded action.",
  },
  {
    id: "tool",
    label: "Tool Call",
    description: "Execute the selected capability.",
  },
  {
    id: "observation",
    label: "Observation",
    description: "Return tool evidence to the Agent.",
  },
  {
    id: "result",
    label: "Result",
    description: "Synthesize or finish the run.",
  },
] as const

const eventStage: Partial<Record<AgentTraceEventType, AgentTimelineStageId>> = {
  plan_ready: "plan",
  tool_call: "tool",
  retry: "tool",
  tool_result: "observation",
  synthesis_ready: "result",
  failure: "result",
  cancelled: "result",
  agent_end: "result",
}

const terminalEventTypes = new Set<AgentTraceEventType>([
  "failure",
  "cancelled",
  "agent_end",
])

export function getAgentTimelineStageId(
  eventType: AgentTraceEventType,
): AgentTimelineStageId | null {
  return eventStage[eventType] ?? null
}

export function getAgentTimelineEventLabel(eventType: AgentTraceEventType): string {
  if (eventType === "agent_start" || eventType === "context_ready") return "Setup"
  const stageId = getAgentTimelineStageId(eventType)
  return agentTimelineStageDefinitions.find((stage) => stage.id === stageId)?.label ?? "Runtime"
}

export function deriveAgentTimelineStages(
  activities: AgentActivityItem[],
  running: boolean,
): AgentTimelineStage[] {
  const primaryActivities = activities.filter((item) => getAgentTimelineStageId(item.eventType))
  const latestStageId = primaryActivities.length > 0
    ? getAgentTimelineStageId(primaryActivities.at(-1)!.eventType)
    : null
  const hasTerminalEvent = activities.some((item) => terminalEventTypes.has(item.eventType))

  return agentTimelineStageDefinitions.map((definition) => {
    const stageActivities = activities.filter(
      (item) => getAgentTimelineStageId(item.eventType) === definition.id,
    )
    const hasWarning = stageActivities.some((item) => item.tone === "warning")

    let status: AgentTimelineStageStatus = "idle"
    if (hasWarning) {
      status = "warning"
    } else if (stageActivities.length > 0) {
      status = running && !hasTerminalEvent && latestStageId === definition.id
        ? "active"
        : "complete"
    } else if (
      running
      && activities.length > 0
      && latestStageId === null
      && definition.id === "plan"
    ) {
      status = "active"
    }

    return {
      ...definition,
      status,
      activityCount: stageActivities.length,
    }
  })
}
