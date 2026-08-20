import { API_BASE_URL } from "../../api/client"
import type { BrowserBridgeStatusResponse } from "../../api/types"
import { desktop } from "../../desktop"

export default function WorkspaceHeader({
  backendState,
  backendService,
  providerName,
  browserStatus,
  browserStatusChecking,
}: {
  backendState: "checking" | "connected" | "offline"
  backendService: string
  providerName: string
  browserStatus: BrowserBridgeStatusResponse | undefined
  browserStatusChecking: boolean
}) {
  const backendLabel = backendState === "checking"
    ? "Checking…"
    : backendState === "connected"
      ? `${backendService} · Connected`
      : `Offline · ${API_BASE_URL}`

  const browserLabel = browserStatus?.running
    ? `Listening · ${browserStatus.port}`
    : browserStatusChecking
      ? "Checking…"
      : "Unavailable / port busy"

  return (
    <header className="rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
            Stage 3 · React Workspace
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">
            AITranslator WebReBuild
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Translation, reading context, native overlay behavior, AI companion, and research notes now live behind explicit frontend feature boundaries.
          </p>
        </div>

        <div className="grid min-w-80 gap-2 text-sm">
          <StatusRow label="Runtime" value={desktop.runtime} />
          <StatusRow label="Backend" value={backendLabel} />
          <StatusRow label="Provider" value={providerName} />
          <StatusRow label="Browser bridge" value={browserLabel} />
        </div>
      </div>
    </header>
  )
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-5 rounded-lg bg-slate-50 px-4 py-2.5">
      <span className="text-slate-500">{label}</span>
      <span className="max-w-52 truncate font-medium capitalize text-slate-900">{value}</span>
    </div>
  )
}
