import { describe, expect, it } from "vitest"

import { computeOverlayPosition } from "./overlay-positioning"

const workArea = { x: 0, y: 0, width: 1920, height: 1040 }
const windowSize = { width: 420, height: 260 }

describe("computeOverlayPosition", () => {
  it("places mouse-follow overlay below and to the right of the cursor", () => {
    expect(
      computeOverlayPosition({
        mode: "mouse_follow",
        cursor: { x: 600, y: 300 },
        windowSize,
        workArea,
      }),
    ).toEqual({ x: 616, y: 316 })
  })

  it("flips left and above when the cursor is near the lower-right edge", () => {
    expect(
      computeOverlayPosition({
        mode: "mouse_follow",
        cursor: { x: 1880, y: 1010 },
        windowSize,
        workArea,
      }),
    ).toEqual({ x: 1444, y: 734 })
  })

  it("clamps correctly on monitors with negative desktop coordinates", () => {
    expect(
      computeOverlayPosition({
        mode: "custom_fixed_position",
        cursor: { x: -1000, y: 200 },
        customPosition: { x: -3000, y: -100 },
        windowSize,
        workArea: { x: -1920, y: 0, width: 1920, height: 1040 },
      }),
    ).toEqual({ x: -1912, y: 8 })
  })

  it("preserves desktop-lyrics placement semantics", () => {
    expect(
      computeOverlayPosition({
        mode: "desktop_lyrics_bottom",
        cursor: { x: 10, y: 10 },
        windowSize,
        workArea,
      }),
    ).toEqual({ x: 750, y: 756 })

    expect(
      computeOverlayPosition({
        mode: "desktop_lyrics_center",
        cursor: { x: 10, y: 10 },
        windowSize,
        workArea,
      }),
    ).toEqual({ x: 750, y: 390 })

    expect(
      computeOverlayPosition({
        mode: "desktop_lyrics_top",
        cursor: { x: 10, y: 10 },
        windowSize,
        workArea,
      }),
    ).toEqual({ x: 750, y: 24 })
  })
})
