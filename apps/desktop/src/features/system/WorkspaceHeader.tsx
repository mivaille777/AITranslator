import { Activity } from "lucide-react"

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
  const backendValue = backendState === "checking"
    ? "Connecting…"
    : backendState === "connected"
      ? backendService
      : `Offline · ${API_BASE_URL}`

  const bridgeValue = browserStatus?.running
    ? `Browser DOM :${browserStatus.port}`
    : browserStatusChecking
      ? "Checking…"
      : "Optional · unavailable"

  const systemDot = backendState === "connected"
    ? "bg-emerald-500"
    : backendState === "offline"
      ? "bg-amber-500"
      : "bg-slate-300"

  return (
    <header className="workspace-header">
      <div className="workspace-header-inner">
        <div className="min-w-0">
          <h1 className="workspace-title">{title}</h1>
          <p className="workspace-description">{description}</p>
        </div>

        <details className="group relative shrink-0">
          <summary className="workspace-status" aria-label="System status details" title="System status">
            <span className={`h-2 w-2 rounded-full ${systemDot}`} />
            <Activity size={14} strokeWidth={1.8} />
          </summary>

          <div className="ait-system-popover absolute right-0 top-full z-50 mt-2 w-[300px] overflow-hidden rounded-[16px] border border-slate-200/80 bg-white/98 p-2.5 shadow-[0_20px_60px_rgba(15,23,42,0.16)] backdrop-blur-xl">
            <p className="px-2 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              System status
            </p>
            <StatusRow label="Backend" value={backendValue} healthy={backendState === "connected"} />
            <StatusRow label="Provider" value={providerName || "Not loaded"} />
            <StatusRow label="Browser bridge" value={bridgeValue} healthy={browserStatus?.running} />
          </div>
        </details>
      </div>
    </header>
  )
}

function StatusRow({ label, value, healthy }: { label: string; value: string; healthy?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-[10px] px-2 py-2 hover:bg-slate-50">
      <div className="flex items-center gap-2 text-xs text-slate-500">
        {healthy !== undefined && <span className={`h-1.5 w-1.5 rounded-full ${healthy ? "bg-emerald-500" : "bg-slate-300"}`} />}
        <span>{label}</span>
      </div>
      <span className="max-w-[170px] break-all text-right text-xs font-medium text-slate-700">{value}</span>
    </div>
  )
}
