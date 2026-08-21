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
    ? `:${browserStatus.port}`
    : browserStatusChecking
      ? "Checking…"
      : "Unavailable"

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/[0.85] px-4 py-4 backdrop-blur-xl sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="flex items-baseline gap-3">
            <h1 className="text-[22px] font-semibold tracking-[-0.025em] text-slate-950">{title}</h1>
            <p className="hidden truncate text-sm text-slate-500 lg:block">{description}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5 text-[11px]">
          <StatusPill
            label="Backend"
            value={backendLabel}
            healthy={backendState === "connected"}
          />
          <StatusPill label="Provider" value={providerName} />
          <StatusPill
            label="Bridge"
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
    <div
      className="flex max-w-72 items-center gap-2 rounded-full border border-slate-200/80 bg-slate-50/90 px-3 py-1.5 text-slate-500 shadow-sm"
      title={`${label}: ${value}`}
    >
      {healthy !== undefined && (
        <span className={`h-1.5 w-1.5 rounded-full ${healthy ? "bg-emerald-500" : "bg-slate-300"}`} />
      )}
      <span className="text-slate-400">{label}</span>
      <span className="truncate font-medium text-slate-700">{value}</span>
    </div>
  )
}
