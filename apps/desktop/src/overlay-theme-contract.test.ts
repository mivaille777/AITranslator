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

  it("treats DWM as the primary desktop blur instead of painting an opaque CSS sheet", () => {
    const source = read("./overlay-theme.css")

    expect(source).toContain("DWM owns the desktop blur")
    expect(source).toContain("--ait-overlay-shell-backdrop: none")
    expect(source).not.toContain("blur(34px)")
    expect(source).not.toContain("rgba(255, 255, 255, 0.76)")
  })

  it("uses one DPI-aware native clip and suppresses the Windows 11 frame border", () => {
    const source = read("../src-tauri/src/main.rs")

    expect(source).toContain("DWMWCP_DONOTROUND")
    expect(source).toContain("DWMWA_BORDER_COLOR")
    expect(source).toContain("DWMWA_COLOR_NONE")
    expect(source).toContain("SetWindowRgn")
  })
})
