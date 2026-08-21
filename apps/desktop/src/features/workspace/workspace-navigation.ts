export type WorkspaceRoutePath =
  | "/translation"
  | "/reading"
  | "/chat"
  | "/agent"
  | "/research"
  | "/settings"

export interface WorkspaceRouteMeta {
  path: WorkspaceRoutePath
  label: string
  description: string
}

export const workspaceRoutes: readonly WorkspaceRouteMeta[] = [
  {
    path: "/translation",
    label: "Translation",
    description: "Translate manual input or the latest reading selection.",
  },
  {
    path: "/reading",
    label: "Reading",
    description: "Inspect the active selection, document identity, section, and nearby context.",
  },
  {
    path: "/chat",
    label: "AI Chat",
    description: "Continue reasoning from a frozen reading or research context.",
  },
  {
    path: "/agent",
    label: "Agent Workspace",
    description: "Manage context, execution trace, and AI agent interactions.",
  },
  {
    path: "/research",
    label: "Research",
    description: "Browse saved reading evidence and reopen it as chat context.",
  },
  {
    path: "/settings",
    label: "Settings",
    description: "Configure native overlay placement and interaction behavior.",
  },
] as const

const fallbackRoute = workspaceRoutes[0]

export function getWorkspaceRouteMeta(pathname: string): WorkspaceRouteMeta {
  return workspaceRoutes.find((route) => route.path === pathname) ?? fallbackRoute
}
