import { describe, expect, it } from "vitest"

import { isExplicitOverlayTranslationIntent } from "./overlay-translation-intent"

describe("overlay translation intent fast path", () => {
  it.each([
    "翻译一下",
    "帮我翻译一下",
    "我要你翻译一下",
    "请翻译这段",
    "把这段翻译一下",
    "翻成英文",
    "translate this",
    "please translate the selection",
  ])("routes explicit translation command %s", (message) => {
    expect(isExplicitOverlayTranslationIntent(message)).toBe(true)
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
