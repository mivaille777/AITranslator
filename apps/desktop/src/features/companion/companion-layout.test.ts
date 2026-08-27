import { describe, expect, it } from "vitest"

import { companionLayoutClassNames } from "./companion-layout"

describe("AI Chat nested scroll layout", () => {
  it("keeps the workspace bounded to the available route height", () => {
    expect(companionLayoutClassNames.shell).toContain("h-full")
    expect(companionLayoutClassNames.shell).toContain("min-h-0")
    expect(companionLayoutClassNames.shell).toContain("overflow-hidden")
  })

  it("gives history, context, and messages their own scroll ownership", () => {
    expect(companionLayoutClassNames.historyPanel).toContain("h-full")
    expect(companionLayoutClassNames.historyScroller).toContain("flex-1")
    expect(companionLayoutClassNames.historyScroller).toContain("overflow-y-auto")
    expect(companionLayoutClassNames.contextPanel).toContain("overflow-y-auto")
    expect(companionLayoutClassNames.messageScroller).toContain("flex-1")
    expect(companionLayoutClassNames.messageScroller).toContain("overflow-y-auto")
    expect(companionLayoutClassNames.messageScroller).toContain("overscroll-contain")
  })

  it("keeps the composer outside the message scroller", () => {
    expect(companionLayoutClassNames.chatColumn).toContain("flex-col")
    expect(companionLayoutClassNames.composer).toContain("shrink-0")
  })
})
