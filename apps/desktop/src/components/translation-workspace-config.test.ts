import { describe, expect, it } from "vitest"

import {
  resolveTranslationLanguageSwap,
  translationProviderLabel,
} from "./translation-workspace-config"

describe("translation workspace configuration", () => {
  it("maps provider identifiers to compact labels", () => {
    expect(translationProviderLabel("youdao_web")).toBe("Youdao")
    expect(translationProviderLabel("google_web")).toBe("Google")
    expect(translationProviderLabel("ai")).toBe("AI")
  })

  it("swaps explicit source and target languages", () => {
    expect(resolveTranslationLanguageSwap("en", "zh-CN")).toEqual({
      sourceLanguage: "zh-CN",
      targetLanguage: "en",
    })
  })

  it("uses a detected source language when auto can be resolved", () => {
    expect(resolveTranslationLanguageSwap("auto", "zh-CN", "en")).toEqual({
      sourceLanguage: "zh-CN",
      targetLanguage: "en",
    })
  })

  it("disables swapping when auto source has no detected language", () => {
    expect(resolveTranslationLanguageSwap("auto", "zh-CN")).toBeNull()
  })
})
