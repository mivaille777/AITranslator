import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

function read(relativePath: string): string {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8")
}

describe("overlay theme material contract", () => {
  it("defines semantic material tokens for both overlay themes", () => {
    const source = read("./overlay-theme.css")

    expect(source).toContain("--ait-overlay-host-background")
    expect(source).toContain("--ait-overlay-shell-background")
    expect(source).toContain("--ait-overlay-surface-background")
    expect(source).toContain("--ait-overlay-control-background")
    expect(source).toContain('[data-ait-overlay-theme="light"]')
    expect(source).toContain('[data-ait-overlay-theme="dark"]')
  })

  it("keeps clipped shell elevation internal instead of relying on a large outer shadow", () => {
    const source = read("./overlay-theme.css")

    expect(source).toContain("--ait-overlay-shell-shadow")
    expect(source).not.toContain("0 22px 62px")
  })

  it("keeps the CSS shell translucent instead of painting an opaque light sheet", () => {
    const source = read("./overlay-theme.css")

    expect(source).toContain("--ait-overlay-shell-backdrop: none")
    expect(source).not.toContain("blur(34px)")
    expect(source).not.toContain("rgba(255, 255, 255, 0.76)")
  })

  it("loads a final dark-ink readability layer for the light theme", () => {
    const entry = read("./overlay-main.tsx")
    const readability = read("./overlay-light-readability.css")

    expect(entry.indexOf('import "./overlay-light-readability.css"')).toBeGreaterThan(
      entry.indexOf('import "./overlay-theme.css"'),
    )
    expect(readability).toContain("--ait-overlay-readable-primary")
    expect(readability).toContain("rgba(16, 24, 40, 0.98)")
    expect(readability).toContain("color: var(--ait-overlay-readable-primary) !important")
    expect(readability).toContain("--ait-overlay-readable-muted")
  })

  it("uses one DPI-aware native clip and suppresses the Windows 11 frame border", () => {
    const source = read("../src-tauri/src/main.rs")

    expect(source).toContain("DWMWCP_DONOTROUND")
    expect(source).toContain("DWMWA_BORDER_COLOR")
    expect(source).toContain("DWMWA_COLOR_NONE")
    expect(source).toContain("SetWindowRgn")
  })
})
