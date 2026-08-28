import { LoaderCircle, ServerOff } from "lucide-react"

import { EmptyState } from "../../shared/ui/EmptyState"
import type { TranslationWorkspaceController } from "../translation/useTranslationWorkspace"
import ResearchScopePanel from "./ResearchScopePanel"
import ResearchWorkspace from "./ResearchWorkspace"

type BackendState = "checking" | "connected" | "offline"

export default function ResearchRoute({
  backendState,
  workspace,
}: {
  backendState: BackendState
  workspace: TranslationWorkspaceController
}) {
  if (backendState === "checking") {
    return (
      <section className="ait-surface overflow-hidden p-7">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <LoaderCircle size={17} className="animate-spin text-slate-400" />
          Connecting Research Workspace…
        </div>
        <div className="mt-6 grid gap-3 lg:grid-cols-[220px_280px_minmax(0,1fr)]">
          <SkeletonBlock className="h-72" />
          <SkeletonBlock className="h-72" />
          <SkeletonBlock className="h-72" />
        </div>
      </section>
    )
  }

  if (backendState === "offline") {
    return (
      <EmptyState
        className="ait-surface border-solid bg-white/90 py-16"
        icon={<ServerOff size={24} strokeWidth={1.6} />}
        title="Research Workspace is waiting for the backend"
        description="Your research data remains local. Start or reconnect the AITranslator backend and this workspace will resume automatically."
      />
    )
  }

  return (
    <div className="space-y-4">
      <ResearchScopePanel workspace={workspace} />
      <ResearchWorkspace />
    </div>
  )
}

function SkeletonBlock({ className }: { className: string }) {
  return (
    <div className={`overflow-hidden rounded-[20px] border border-slate-200/60 bg-slate-50/70 p-4 ${className}`}>
      <div className="ait-skeleton h-4 w-24 rounded-full" />
      <div className="ait-skeleton mt-5 h-10 w-full rounded-[12px]" />
      <div className="ait-skeleton mt-3 h-10 w-[86%] rounded-[12px]" />
      <div className="ait-skeleton mt-3 h-24 w-full rounded-[16px]" />
    </div>
  )
}
