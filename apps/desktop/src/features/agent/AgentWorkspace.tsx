import type { TranslationWorkspaceController } from "../translation/useTranslationWorkspace"
import { AgentHeader } from "../companion/components/AgentHeader"
import { AgentInputComposer } from "../companion/components/AgentInputComposer"
import { AgentMessage } from "../companion/components/AgentMessage"
import { AgentObservabilityPanel } from "../companion/components/AgentObservabilityPanel"
import { AgentTrace } from "../companion/components/AgentTrace"
import { ContextCard } from "../companion/components/ContextCard"
import { agentWorkspaceAreas } from "./agent-workspace-layout"
import { useAgentRuntime } from "./hooks/useAgentRuntime"

export function AgentWorkspace({ workspace }: { workspace: TranslationWorkspaceController }) {
  const runtime = useAgentRuntime(workspace)

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
            Runtime state now belongs to the Agent feature while the existing tested presentation components remain reusable.
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

      <AgentHeader phase={runtime.viewState.phase} uiMode={runtime.viewState.uiMode} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <ContextCard
          text={runtime.sourceText}
          title={runtime.context.resource_title}
          section={runtime.context.section_heading}
          sourceKind={runtime.context.source_kind}
        />
        <AgentTrace
          activities={runtime.viewState.activities}
          running={runtime.viewState.phase === "running" || runtime.viewState.phase === "cancelling"}
          runId={runtime.viewState.runId}
          traceId={runtime.viewState.traceId}
          totalDurationMs={runtime.viewState.totalDurationMs}
        />
      </div>

      <AgentMessage
        content={runtime.viewState.outputText}
        phase={runtime.viewState.phase}
        provider={runtime.viewState.provider}
        model={runtime.viewState.model}
        confirmationTool={runtime.viewState.confirmationTool}
        errorMessage={runtime.viewState.errorMessage}
        onConfirm={runtime.confirmWriteTool}
        confirming={runtime.pending}
      />

      <AgentObservabilityPanel
        refreshToken={runtime.observabilityRefresh}
        currentRunId={runtime.viewState.runId}
      />

      <AgentInputComposer
        value={runtime.prompt}
        onChange={runtime.setPrompt}
        onSubmit={runtime.submitPrompt}
        onCancel={runtime.cancelRun}
        disabled={runtime.pending}
        busy={runtime.pending}
        cancelling={runtime.cancelRequested}
      />
    </section>
  )
}

export default AgentWorkspace
