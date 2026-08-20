import { API_BASE_URL } from "../../api/client"
import type { BrowserBridgeStatusResponse } from "../../api/types"

export default function WorkspaceHeader({
  title,
  description,
  backendState,
  backendService,
  providerName,
  browserStatus,
  browserStatusChecking,
}: {
  title: string
  description: string
  backendState: "checking" | "connected" | "offline"
  backendService: string
  providerName: string
  browserStatus: BrowserBridgeStatusResponse | undefined
  browserStatusChecking: boolean
}) {
  const backendLabel = backendState === "checking"
    ? "Checking…"
    : backendState === "connected"
      ? backendService
      : `Offline · ${API_BASE_URL}`

  const browserLabel = browserStatus?.running
    ? `Bridge :${browserStatus.port}`
    : browserStatusChecking
      ? "Bridge checking…"
      : "Bridge unavailable"

  return (
    <header className="border-b border-slate-200 bg-white/95 px-4 py-4 backdrop-blur sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">
            Stage 3 · Workspace
          </p>
          <div className="mt-1 flex items-baseline gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-slate-950">{title}</h1>
            <p className="hidden truncate text-sm text-slate-500 lg:block">{description}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 text-[11px]">
          <StatusPill
            label="Backend"
            value={backendLabel}
            healthy={backendState === "connected"}
          />
          <StatusPill label="Provider" value={providerName} />
          <StatusPill
            label="Browser"
            value={browserLabel}
            healthy={Boolean(browserStatus?.running)}
          />
        </div>
      </div>
    </header>
  )
}

function StatusPill({
  label,
  value,
  healthy,
}: {
  label: string
  value: string
  healthy?: boolean
}) {
  return (
    <div className="flex max-w-72 items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-slate-500">
      {healthy !== undefined && (
        <span className={`h-1.5 w-1.5 rounded-full ${healthy ? "bg-emerald-500" : "bg-slate-300"}`} />
      )}
      <span>{label}</span>
      <span className="truncate font-medium text-slate-800">{value}</span>
    </div>
  )
}
