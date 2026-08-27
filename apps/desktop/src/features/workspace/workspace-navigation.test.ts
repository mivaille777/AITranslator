import { describe, expect, it } from "vitest"

import {
  getWorkspaceRouteMeta,
  workspaceRoutes,
  workspaceRouteUsesFixedHeight,
} from "./workspace-navigation"

describe("workspace navigation", () => {
  it("defines unique workspace paths", () => {
    const paths = workspaceRoutes.map((route) => route.path)
    expect(new Set(paths).size).toBe(paths.length)
    expect(paths).toEqual([
      "/translation",
      "/reading",
      "/chat",
      "/agent",
      "/knowledge",
      "/research",
      "/settings",
    ])
  })

  it("returns metadata for a known route", () => {
    expect(getWorkspaceRouteMeta("/chat").label).toBe("AI Chat")
  })

  it("falls back to Translation for unknown routes", () => {
    expect(getWorkspaceRouteMeta("/unknown").path).toBe("/translation")
  })

  it("reserves whole-workspace scrolling for chat's internal panes", () => {
    expect(workspaceRouteUsesFixedHeight("/chat")).toBe(true)
    expect(workspaceRouteUsesFixedHeight("/translation")).toBe(false)
    expect(workspaceRouteUsesFixedHeight("/knowledge")).toBe(false)
    expect(workspaceRouteUsesFixedHeight("/settings")).toBe(false)
  })
})
