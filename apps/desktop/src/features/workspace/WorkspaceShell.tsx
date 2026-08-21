import type { ReactNode } from "react"
import {
  BookOpenText,
  Bot,
  Languages,
  MessageSquareText,
  NotebookText,
  Settings2,
  Sparkles,
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
  "/agent": Bot,
  "/research": NotebookText,
  "/settings": Settings2,
} as const

export default function WorkspaceShell({ children, backendState, backendService, providerName, browserStatus, browserStatusChecking }: {
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
      <div className="h-full bg-transparent text-slate-950 md:flex">
        <aside className="w-[22%] min-w-[220px] p-3">
          <div className="flex h-full flex-col rounded-[24px] border border-white/10 bg-[#070a17]/95 text-slate-200 shadow-[0_18px_50px_rgba(15,23,42,0.2)] backdrop-blur-xl">
            <div className="px-5 pb-5 pt-5">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-[12px] bg-white text-sm font-semibold text-slate-900">A</span>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">AITranslator</p>
                  <p className="text-sm font-semibold text-white">WebReBuild</p>
                </div>
              </div>
            </div>

            <nav className="flex flex-1 flex-col gap-1 px-3">
              {workspaceRoutes.map((route) => {
                const Icon = icons[route.path]
                return (
                  <NavLink key={route.path} to={route.path} className={({ isActive }) => `group flex items-center gap-3 rounded-[14px] px-3.5 py-3 text-sm font-medium transition-all duration-200 ${isActive ? "bg-white/[0.12] text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]" : "text-slate-400 hover:bg-white/[0.055] hover:text-white"}`}>
                    <span className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-white/[0.035] transition-transform duration-200 group-hover:scale-105">
                      <Icon size={16} strokeWidth={1.8} />
                    </span>
                    {route.label}
                  </NavLink>
                )
              })}
            </nav>

            <div className="px-4 pb-4">
              <div className="rounded-[18px] border border-white/[0.08] bg-white/[0.04] px-3 py-3 text-[11px]">
                <div className="flex items-center gap-2 text-slate-200">
                  <Sparkles size={14} />
                  <span className="font-medium">AI Agent</span>
                </div>
                <div className="mt-2 flex items-center gap-2 text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  Online
                </div>
                <p className="mt-2 text-slate-400">{providerName || desktop.runtime}</p>
              </div>
            </div>
          </div>
        </aside>

        <div className="min-w-0 flex-1 p-3 pl-0">
          <div className="h-full overflow-hidden rounded-[24px] border border-white/50 bg-white/75 shadow-[0_16px_48px_rgba(15,23,42,0.1)] backdrop-blur-xl">
            <WorkspaceHeader title={routeMeta.label} description={routeMeta.description} backendState={backendState} backendService={backendService} providerName={providerName} browserStatus={browserStatus} browserStatusChecking={browserStatusChecking} />
            <main className="h-[calc(100%-64px)] overflow-auto px-4 py-5 sm:px-6 lg:px-8 lg:py-7 workspace-route-enter">{children}</main>
          </div>
        </div>
      </div>
    </WindowFrame>
  )
}
