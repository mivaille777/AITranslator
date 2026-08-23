import type { TranslationWorkspaceController } from "../translation/useTranslationWorkspace"
import { AgentWorkspace as RuntimeAgentWorkspace } from "../companion/AgentWorkspace"
import { agentWorkspaceAreas } from "./agent-workspace-layout"

export function AgentWorkspace({ workspace }: { workspace: TranslationWorkspaceController }) {
  return (
    <section aria-label="Agent Workspace" className="space-y-4">
      <div className="ait-surface overflow-hidden p-5 sm:p-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-2xl">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">
              Stage 9 · Agent-first workspace
            </p>
            <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-950">
              One workspace for context, tools, and execution
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Translation, reading, and research capabilities are presented as Agent resources instead of separate hidden execution paths.
            </p>
          </div>
          <p className="max-w-md text-xs leading-5 text-slate-400">
            Stage 9.1 establishes the product boundary while preserving the existing tested streaming Agent runtime underneath it.
          </p>
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-4" aria-label="Agent workspace areas">
          {agentWorkspaceAreas.map((area, index) => (
            <div
              key={area.id}
              className="rounded-[16px] border border-slate-200/80 bg-white/70 px-4 py-3 shadow-sm"
              data-agent-area={area.id}
            >
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-semibold tabular-nums text-slate-400">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <strong className="text-xs font-semibold text-slate-800">{area.label}</strong>
              </div>
              <p className="mt-2 text-[11px] leading-5 text-slate-500">{area.description}</p>
            </div>
          ))}
        </div>
      </div>

      <RuntimeAgentWorkspace workspace={workspace} />
    </section>
  )
}

export default AgentWorkspace
