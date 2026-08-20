import type { ReactNode } from "react"
import {
  BookOpenText,
  Languages,
  MessageSquareText,
  NotebookText,
  Settings2,
} from "lucide-react"
import { NavLink, useLocation } from "react-router-dom"

import type { BrowserBridgeStatusResponse } from "../../api/types"
import { desktop } from "../../desktop"
import WorkspaceHeader from "../system/WorkspaceHeader"
import { getWorkspaceRouteMeta, workspaceRoutes } from "./workspace-navigation"

const icons = {
  "/translation": Languages,
  "/reading": BookOpenText,
  "/chat": MessageSquareText,
  "/research": NotebookText,
  "/settings": Settings2,
} as const

export default function WorkspaceShell({
  children,
  backendState,
  backendService,
  providerName,
  browserStatus,
  browserStatusChecking,
}: {
  children: ReactNode
  backendState: "checking" | "connected" | "offline"
  backendService: string
  providerName: string
  browserStatus: BrowserBridgeStatusResponse | undefined
  browserStatusChecking: boolean
}) {
  const location = useLocation()
  const routeMeta = getWorkspaceRouteMeta(location.pathname)

  return (
    <div className="min-h-screen bg-slate-100 text-slate-950 md:grid md:grid-cols-[224px_minmax(0,1fr)]">
      <aside className="border-b border-slate-800 bg-slate-950 text-slate-200 md:sticky md:top-0 md:h-screen md:border-b-0 md:border-r">
        <div className="flex h-full flex-col">
          <div className="px-5 py-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
              AITranslator
            </p>
            <p className="mt-1 text-base font-semibold tracking-tight text-white">WebReBuild</p>
          </div>

          <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:overflow-visible md:pb-0">
            {workspaceRoutes.map((route) => {
              const Icon = icons[route.path]
              return (
                <NavLink
                  key={route.path}
                  to={route.path}
                  className={({ isActive }) =>
                    `flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                      isActive
                        ? "bg-white/10 text-white"
                        : "text-slate-400 hover:bg-white/[0.06] hover:text-slate-100"
                    }`
                  }
                >
                  <Icon size={16} strokeWidth={1.8} />
                  {route.label}
                </NavLink>
              )
            })}
          </nav>

          <div className="hidden px-4 pb-5 pt-4 text-[11px] text-slate-500 md:block">
            <div className="rounded-xl border border-white/5 bg-white/[0.03] px-3 py-2.5">
              <p className="font-medium text-slate-400">Desktop runtime</p>
              <p className="mt-1 capitalize text-slate-300">{desktop.runtime}</p>
            </div>
          </div>
        </div>
      </aside>

      <div className="min-w-0">
        <WorkspaceHeader
          title={routeMeta.label}
          description={routeMeta.description}
          backendState={backendState}
          backendService={backendService}
          providerName={providerName}
          browserStatus={browserStatus}
          browserStatusChecking={browserStatusChecking}
        />
        <main className="mx-auto w-full max-w-[1500px] px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
          {children}
        </main>
      </div>
    </div>
  )
}
