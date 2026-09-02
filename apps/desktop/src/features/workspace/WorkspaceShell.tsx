import type { ReactNode } from "react"
import {
  BookOpenText,
  Bot,
  Languages,
  MessageSquareText,
  NotebookText,
  LibraryBig,
  Settings2,
  Sparkles,
} from "lucide-react"
import { NavLink, useLocation } from "react-router-dom"

import type { BrowserBridgeStatusResponse } from "../../api/types"
import { desktop } from "../../desktop"
import WindowFrame from "../../components/WindowFrame"
import WorkspaceHeader from "../system/WorkspaceHeader"
import {
  getWorkspaceRouteMeta,
  workspaceRoutes,
  workspaceRouteUsesFixedHeight,
} from "./workspace-navigation"

const icons = {
  "/translation": Languages,
  "/reading": BookOpenText,
  "/chat": MessageSquareText,
  "/agent": Bot,
  "/knowledge": LibraryBig,
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
  const fixedHeightRoute = workspaceRouteUsesFixedHeight(location.pathname)

  return (
    <WindowFrame>
      <div className="ait-app-shell grid h-full min-h-0 grid-rows-[minmax(0,1fr)] overflow-hidden bg-transparent text-slate-950 md:grid-cols-[208px_minmax(0,1fr)]">
        <aside className="ait-global-nav min-h-0 overflow-hidden p-3 pr-0">
          <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-[22px] border border-white/[0.08] bg-[#07101f] text-slate-200 shadow-[0_18px_48px_rgba(15,23,42,0.18)]">
            <div className="shrink-0 px-4 pb-4 pt-5">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-white text-sm font-semibold text-slate-950">A</span>
                <div className="min-w-0">
                  <p className="text-[9px] font-semibold uppercase tracking-[0.22em] text-slate-500">AITranslator</p>
                  <p className="truncate text-sm font-semibold text-white">WebReBuild</p>
                </div>
              </div>
            </div>

            <nav className="ait-scroll-dark min-h-0 flex-1 overflow-y-auto overscroll-contain px-2.5 pb-2">
              <div className="flex min-h-max flex-col gap-1">
                {workspaceRoutes.map((route) => {
                  const Icon = icons[route.path]
                  return (
                    <NavLink
                      key={route.path}
                      to={route.path}
                      className={({ isActive }) => `group flex items-center gap-2.5 rounded-[11px] px-2.5 py-2.5 text-[13px] font-medium transition-all duration-200 ${
                        isActive
                          ? "bg-[#17366f] text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.045)]"
                          : "text-slate-400 hover:bg-white/[0.055] hover:text-white"
                      }`}
                    >
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[9px] bg-white/[0.04] transition-transform duration-200 group-hover:scale-[1.04]">
                        <Icon size={15} strokeWidth={1.8} />
                      </span>
                      <span className="truncate">{route.label}</span>
                    </NavLink>
                  )
                })}
              </div>
            </nav>

            <div className="shrink-0 px-3 pb-3 pt-1">
              <div className="rounded-[16px] border border-white/[0.08] bg-white/[0.035] px-3 py-3 text-[11px]">
                <div className="flex items-center gap-2 text-slate-200">
                  <Sparkles size={13} />
                  <span className="font-medium">AI Agent</span>
                </div>
                <div className="mt-2 flex items-center gap-2 text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  Online
                </div>
                <p className="mt-2 truncate text-slate-500">{providerName || desktop.runtime}</p>
              </div>
            </div>
          </div>
        </aside>

        <div className="min-h-0 min-w-0 overflow-hidden p-3">
          <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-[22px] border border-slate-200/70 bg-white shadow-[0_16px_44px_rgba(15,23,42,0.08)]">
            <WorkspaceHeader
              title={routeMeta.label}
              description={routeMeta.description}
              backendState={backendState}
              backendService={backendService}
              providerName={providerName}
              browserStatus={browserStatus}
              browserStatusChecking={browserStatusChecking}
            />
            <main
              className={`min-h-0 flex-1 workspace-route-enter ${
                fixedHeightRoute
                  ? "overflow-hidden"
                  : "ait-scroll-page overflow-y-auto overflow-x-hidden overscroll-contain"
              }`}
            >
              <div className={fixedHeightRoute ? "h-full min-h-0 overflow-hidden" : "px-5 py-5 lg:px-6 lg:py-6"}>
                {children}
              </div>
            </main>
          </div>
        </div>
      </div>
    </WindowFrame>
  )
}
