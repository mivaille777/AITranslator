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
import WindowFrame from "../../components/WindowFrame"
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
    <WindowFrame>
      <div className="h-full bg-[#f2f5f9] text-slate-950 md:flex">
        <aside className="w-[22%] min-w-[220px] p-3">
          <div className="flex h-full flex-col rounded-[22px] border border-white/40 bg-[#070a17] text-slate-200 shadow-[0_14px_40px_rgba(15,23,42,0.16)]">
            <div className="px-5 pb-6 pt-6">
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">AITranslator</p>
              <p className="mt-1.5 text-base font-semibold tracking-tight text-white">WebReBuild</p>
            </div>

            <nav className="flex flex-1 flex-col gap-1 px-3">
              {workspaceRoutes.map((route) => {
                const Icon = icons[route.path]
                return (
                  <NavLink
                    key={route.path}
                    to={route.path}
                    className={({ isActive }) =>
                      `group flex items-center gap-3 rounded-[14px] px-3.5 py-3 text-sm font-medium transition-all duration-200 ${
                        isActive
                          ? "bg-white/[0.12] text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]"
                          : "text-slate-400 hover:bg-white/[0.055] hover:text-slate-100"
                      }`
                    }
                  >
                    <span className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-white/[0.035] transition-transform duration-200 group-hover:scale-105">
                      <Icon size={16} strokeWidth={1.8} />
                    </span>
                    {route.label}
                  </NavLink>
                )
              })}
            </nav>

            <div className="px-4 pb-4 text-[11px] text-slate-500">
              <div className="rounded-[16px] border border-white/[0.06] bg-white/[0.035] px-3 py-3">
                <p className="font-medium">Desktop runtime</p>
                <p className="mt-1 capitalize text-slate-300">{desktop.runtime}</p>
              </div>
            </div>
          </div>
        </aside>

        <div className="min-w-0 flex-1 p-3 pl-0">
          <div className="h-full overflow-hidden rounded-[22px] border border-white/50 bg-white/70 shadow-[0_12px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl">
            <WorkspaceHeader
              title={routeMeta.label}
              description={routeMeta.description}
              backendState={backendState}
              backendService={backendService}
              providerName={providerName}
              browserStatus={browserStatus}
              browserStatusChecking={browserStatusChecking}
            />
            <main className="h-[calc(100%-64px)] overflow-auto px-4 py-5 sm:px-6 lg:px-8 lg:py-7">{children}</main>
          </div>
        </div>
      </div>
    </WindowFrame>
  )
}
