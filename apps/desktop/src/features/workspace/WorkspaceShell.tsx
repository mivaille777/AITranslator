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
      <div className="h-full bg-[#f2f5f9] text-slate-950 md:grid md:grid-cols-[22%_78%]">
        <aside className="bg-[#070a17] text-slate-200">
          <div className="flex h-full flex-col">
            <div className="px-5 pb-6 pt-6">
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">AITranslator</p>
              <p className="mt-1.5 text-base font-semibold text-white">WebReBuild</p>
            </div>
            <nav className="flex flex-1 flex-col gap-1 px-3">
              {workspaceRoutes.map((route) => {
                const Icon = icons[route.path]
                return (
                  <NavLink key={route.path} to={route.path} className={({ isActive }) => `flex items-center gap-3 rounded-[14px] px-3.5 py-3 text-sm ${isActive ? "bg-white/[0.11] text-white" : "text-slate-400 hover:bg-white/[0.055]"}`}>
                    <span className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-white/[0.035]"><Icon size={16} /></span>
                    {route.label}
                  </NavLink>
                )
              })}
            </nav>
          </div>
        </aside>
        <div className="min-w-0">
          <WorkspaceHeader title={routeMeta.label} description={routeMeta.description} backendState={backendState} backendService={backendService} providerName={providerName} browserStatus={browserStatus} browserStatusChecking={browserStatusChecking} />
          <main className="mx-auto w-full max-w-[1500px] px-4 py-5 sm:px-6 lg:px-8 lg:py-7">{children}</main>
        </div>
      </div>
    </WindowFrame>
  )
}
