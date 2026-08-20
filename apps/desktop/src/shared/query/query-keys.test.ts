import { describe, expect, it } from "vitest"

import { queryKeys, queryPolling } from "./query-keys"

describe("query key registry", () => {
  it("shares the companion handoff key across observers", () => {
    expect(queryKeys.companion.handoff).toEqual(["companion", "handoff"])
  })

  it("separates Research Note caches by requested limit", () => {
    expect(queryKeys.research.notes(5)).toEqual(["research", "notes", 5])
    expect(queryKeys.research.notes(20)).toEqual(["research", "notes", 20])
  })

  it("keeps browser selection polling faster than page metadata polling", () => {
    expect(queryPolling.browserSelection).toBeLessThan(queryPolling.browserPage)
  })
})
