import { describe, expect, it } from "vitest"

import {
  resolvePreferredTranslationTarget,
  resolveTranslationLanguageSwap,
  translationProviderLabel,
} from "./translation-workspace-config"

describe("translation workspace configuration", () => {
  it("maps provider identifiers to compact labels", () => {
    expect(translationProviderLabel("youdao_web")).toBe("Youdao")
    expect(translationProviderLabel("google_web")).toBe("Google")
    expect(translationProviderLabel("ai")).toBe("AI")
    expect(translationProviderLabel("ai/deepseek-chat")).toBe("AI")
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

  it("avoids Chinese-to-Chinese no-op for a generic translation command", () => {
    expect(resolvePreferredTranslationTarget(
      "人工智能翻译；分析段落的作用；研究笔记库。",
      "auto",
      "zh-CN",
    )).toBe("en")
  })

  it("keeps an explicit cross-language target unchanged", () => {
    expect(resolvePreferredTranslationTarget("hello world", "en", "zh-CN")).toBe("zh-CN")
  })

  it("avoids an explicit same-language target", () => {
    expect(resolvePreferredTranslationTarget("hello world", "en", "en")).toBe("zh-CN")
  })
})
