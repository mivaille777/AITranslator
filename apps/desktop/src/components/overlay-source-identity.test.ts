import { describe, expect, it } from "vitest"

import { resolveOverlaySourceIdentity } from "./overlay-source-identity"

describe("overlay source identity", () => {
  it("shows a concise Chrome browser identity", () => {
    const identity = resolveOverlaySourceIdentity({
      application: "chrome.exe",
      sourceKind: "browser",
      resourceUrl: "https://chatgpt.com/g/g-p-example/c/123",
      resourceTitle: "AITrans - Agent架构设计",
    })

    expect(identity.applicationLabel).toBe("Chrome")
    expect(identity.badge).toBe("BROWSER")
    expect(identity.detail).toBe("chatgpt.com")
    expect(identity.title).toBe("AITrans - Agent架构设计")
  })

  it("maps Edge PDF and Word sources without exposing paths", () => {
    expect(resolveOverlaySourceIdentity({
      application: "msedge.exe",
      sourceKind: "pdf",
      resourceTitle: "paper.pdf",
    })).toMatchObject({
      applicationLabel: "Edge",
      badge: "PDF",
      title: "paper.pdf",
    })

    expect(resolveOverlaySourceIdentity({
      application: "WINWORD.EXE",
      sourceKind: "word",
      resourceTitle: "EAAI08202146.docx",
    })).toMatchObject({
      applicationLabel: "Word",
      badge: "WORD",
      title: "EAAI08202146.docx",
    })
  })

  it("falls back to source family when an executable name is unavailable", () => {
    const identity = resolveOverlaySourceIdentity({
      sourceKind: "browser",
      resourceUrl: "https://www.example.com/article",
    })

    expect(identity.applicationLabel).toBe("Browser")
    expect(identity.detail).toBe("example.com")
    expect(identity.title).toBe("example.com")
  })
})
