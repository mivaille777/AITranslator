import { describe, expect, it } from "vitest"

import {
  isExplicitOverlayTranslationIntent,
  resolveExplicitOverlayTranslationIntent,
} from "./overlay-translation-intent"

describe("overlay translation intent fast path", () => {
  it.each([
    "翻译一下",
    "帮我翻译一下",
    "我要你翻译一下",
    "请翻译这段",
    "把这段翻译一下",
    "translate this",
    "please translate the selection",
  ])("routes explicit translation command %s", (message) => {
    expect(isExplicitOverlayTranslationIntent(message)).toBe(true)
  })

  it("maps an explicit target-language command", () => {
    expect(resolveExplicitOverlayTranslationIntent("翻成英文")).toEqual({
      targetLanguage: "en",
    })
    expect(resolveExplicitOverlayTranslationIntent("翻成中文")).toEqual({
      targetLanguage: "zh-CN",
    })
  })

  it.each([
    "为什么这里用了翻译模型？",
    "解释一下这段话",
    "translation quality is important",
    "你觉得应该翻译还是总结？",
  ])("does not hijack ambiguous conversation %s", (message) => {
    expect(isExplicitOverlayTranslationIntent(message)).toBe(false)
  })
})
