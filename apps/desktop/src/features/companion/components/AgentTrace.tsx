import { Check, Circle, TriangleAlert } from "lucide-react"

import { AITPanel } from "@/shared/components/AITPanel"
import type { AgentActivityItem } from "../agent-workspace-state"

function ActivityIcon({ item }: { item: AgentActivityItem }) {
  if (item.tone === "warning") return <TriangleAlert size={14} />
  if (item.tone === "success") return <Check size={14} />
  return <Circle size={12} />
}

export function AgentTrace({
  activities,
  running,
  runId,
  traceId,
  totalDurationMs,
}: {
  activities: AgentActivityItem[]
  running: boolean
  runId: string
  traceId: string
  totalDurationMs: number
}) {
  return (
    <AITPanel className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Agent Trace</p>
          <p className="mt-1 text-sm font-medium text-slate-800">Runtime activity</p>
          {runId || traceId ? (
            <p className="mt-1 max-w-[520px] truncate font-mono text-[10px] text-slate-400">
              {[runId, traceId].filter(Boolean).join(" · ")}
            </p>
          ) : null}
        </div>
        <div className="text-right text-xs text-slate-500">
          {running ? <span>Processing…</span> : totalDurationMs > 0 ? <span>{totalDurationMs} ms</span> : null}
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {activities.length === 0 ? (
          <div className="rounded-[14px] border border-dashed border-slate-200 bg-slate-50/70 px-4 py-5 text-sm text-slate-500">
            Run the Agent to inspect context, planning, retries, tools, synthesis, and completion state.
          </div>
        ) : (
          activities.map((item) => (
            <div
              key={`${item.sequence}-${item.eventType}`}
              className="flex items-start gap-3 rounded-[14px] border border-slate-100 bg-slate-50/70 px-3.5 py-3"
            >
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white text-slate-600 shadow-sm">
                <ActivityIcon item={item} />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-800">{item.label}</p>
                <p className="mt-0.5 truncate text-xs text-slate-500">{item.detail}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </AITPanel>
  )
}
