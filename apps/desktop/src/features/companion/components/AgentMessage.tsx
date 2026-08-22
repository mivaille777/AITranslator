import { Bot, CheckCircle2, ShieldAlert } from "lucide-react"

import { AITPanel } from "@/shared/components/AITPanel"
import type { AgentWorkspacePhase } from "../agent-workspace-state"

export function AgentMessage({
  content,
  phase,
  provider,
  model,
  confirmationTool,
  errorMessage,
  onConfirm,
  confirming,
}: {
  content: string
  phase: AgentWorkspacePhase
  provider: string
  model: string
  confirmationTool: string
  errorMessage: string
  onConfirm: () => void
  confirming: boolean
}) {
  const waitingForConfirmation = phase === "confirmation_required" && confirmationTool
  const cancelled = phase === "cancelled"

  return (
    <AITPanel className="p-5">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
        <Bot size={16} />
        Agent response
      </div>

      {phase === "idle" ? (
        <p className="mt-4 text-sm leading-6 text-slate-500">
          The Agent response will appear here after a traced run.
        </p>
      ) : null}

      {phase === "running" && !content ? (
        <p className="mt-4 text-sm leading-6 text-slate-500">Planning and executing the bounded workflow…</p>
      ) : null}

      {phase === "cancelling" && !content ? (
        <p className="mt-4 text-sm leading-6 text-slate-500">Cancellation requested. Waiting for a safe checkpoint…</p>
      ) : null}

      {content ? (
        <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-800">{content}</p>
      ) : null}

      {errorMessage ? (
        <div className={`mt-4 rounded-[14px] border px-4 py-3 text-sm ${cancelled ? "border-amber-200 bg-amber-50 text-amber-800" : "border-rose-200 bg-rose-50 text-rose-700"}`}>
          {errorMessage}
        </div>
      ) : null}

      {waitingForConfirmation ? (
        <div className="mt-4 rounded-[16px] border border-amber-200 bg-amber-50/80 p-4">
          <div className="flex items-start gap-3">
            <ShieldAlert size={18} className="mt-0.5 shrink-0 text-amber-700" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-amber-950">Write action requires confirmation</p>
              <p className="mt-1 text-xs leading-5 text-amber-800">
                The Agent requested <span className="font-mono">{confirmationTool}</span>. It has not been executed yet.
              </p>
              <button
                type="button"
                onClick={onConfirm}
                disabled={confirming}
                className="mt-3 inline-flex items-center gap-2 rounded-[11px] bg-amber-950 px-3 py-2 text-xs font-semibold text-white transition hover:bg-amber-900 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <CheckCircle2 size={14} />
                {confirming ? "Confirming…" : "Confirm and execute"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {provider || model ? (
        <p className="mt-4 text-[11px] text-slate-400">
          {[provider, model].filter(Boolean).join(" · ")}
        </p>
      ) : null}
    </AITPanel>
  )
}
