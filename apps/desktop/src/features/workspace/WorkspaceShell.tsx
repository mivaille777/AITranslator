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
    <div className="min-h-screen bg-[#f2f5f9] text-slate-950 md:grid md:grid-cols-[236px_minmax(0,1fr)]">
      <aside className="border-b border-white/5 bg-[#070a17] text-slate-200 md:sticky md:top-0 md:h-screen md:border-b-0 md:border-r md:border-white/5">
        <div className="flex h-full flex-col">
          <div className="px-5 pb-6 pt-6">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
              AITranslator
            </p>
            <p className="mt-1.5 text-base font-semibold tracking-tight text-white">WebReBuild</p>
          </div>

          <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:overflow-visible md:pb-0">
            {workspaceRoutes.map((route) => {
              const Icon = icons[route.path]
              return (
                <NavLink
                  key={route.path}
                  to={route.path}
                  className={({ isActive }) =>
                    `ait-control-motion group relative flex shrink-0 items-center gap-3 overflow-hidden rounded-[14px] px-3.5 py-3 text-sm font-medium ${
                      isActive
                        ? "bg-white/[0.11] text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]"
                        : "text-slate-400 hover:bg-white/[0.055] hover:text-slate-100"
                    }`
                  }
                >
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[10px] bg-white/[0.035] transition-colors group-hover:bg-white/[0.07]">
                    <Icon size={16} strokeWidth={1.8} />
                  </span>
                  <span>{route.label}</span>
                </NavLink>
              )
            })}
          </nav>

          <div className="hidden px-4 pb-5 pt-4 text-[11px] text-slate-500 md:block">
            <div className="rounded-[18px] border border-white/[0.06] bg-white/[0.035] px-3.5 py-3">
              <p className="font-medium text-slate-500">Desktop runtime</p>
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
