import { describe, expect, it } from "vitest"

import { resolveLanguageSwap } from "./translation-utils"

describe("resolveLanguageSwap", () => {
  it("uses the detected language when swapping from auto", () => {
    expect(resolveLanguageSwap({
      sourceLanguage: "auto",
      targetLanguage: "zh-CN",
      detectedSourceLanguage: "ja",
    })).toEqual({
      sourceLanguage: "zh-CN",
      targetLanguage: "ja",
    })
  })

  it("falls back to English when auto has no detected language", () => {
    expect(resolveLanguageSwap({
      sourceLanguage: "auto",
      targetLanguage: "zh-CN",
    })).toEqual({
      sourceLanguage: "zh-CN",
      targetLanguage: "en",
    })
  })

  it("swaps explicit source and target languages directly", () => {
    expect(resolveLanguageSwap({
      sourceLanguage: "en",
      targetLanguage: "ja",
      detectedSourceLanguage: "ko",
    })).toEqual({
      sourceLanguage: "ja",
      targetLanguage: "en",
    })
  })
})
