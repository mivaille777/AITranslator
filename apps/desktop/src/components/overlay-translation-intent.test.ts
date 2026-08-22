import { describe, expect, it } from "vitest"

import { resolveOverlayControlIntent } from "./overlay-interaction-intent"
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
    "能不能把选中的内容翻译一下？",
    "进入翻译模式",
    "继续翻译",
    "translate this",
    "please translate the selection",
    "can you translate this?",
    "switch to translation mode",
  ])("routes explicit translation command %s", (message) => {
    expect(isExplicitOverlayTranslationIntent(message)).toBe(true)
  })

  it("maps explicit target-language commands", () => {
    expect(resolveExplicitOverlayTranslationIntent("翻成英文")).toEqual({
      targetLanguage: "en",
    })
    expect(resolveExplicitOverlayTranslationIntent("帮我把这段翻译成中文")).toEqual({
      targetLanguage: "zh-CN",
    })
    expect(resolveExplicitOverlayTranslationIntent("可以把它译为日语吗？")).toEqual({
      targetLanguage: "ja",
    })
  })

  it.each([
    "翻译完了",
    "翻译好了",
    "退出翻译模式",
    "结束翻译",
    "不用再翻译了",
    "回到聊天",
    "返回助手",
    "继续对话",
    "done translating",
    "exit translation mode",
    "back to assistant",
  ])("exits translation mode for explicit command %s", (message) => {
    expect(resolveOverlayControlIntent(message, "translation")).toEqual({
      action: "exit_translation",
    })
  })

  it("only treats exit commands as controls while translation is active", () => {
    expect(resolveOverlayControlIntent("退出翻译模式", "assistant")).toBeNull()
    expect(resolveOverlayControlIntent("回到聊天", "assistant")).toBeNull()
  })

  it.each([
    "翻译完了之后帮我解释第三句",
    "为什么要退出翻译模式？",
    "如果翻译结束了再告诉我",
    "退出翻译模式是不是更好？",
    "why should I exit translation mode?",
  ])("does not swallow compound or conversational command-like text %s", (message) => {
    expect(resolveOverlayControlIntent(message, "translation")).toBeNull()
  })

  it.each([
    "为什么这里用了翻译模型？",
    "解释一下这段话",
    "translation quality is important",
    "你觉得应该翻译还是总结？",
    "英文",
  ])("does not hijack ambiguous conversation %s", (message) => {
    expect(isExplicitOverlayTranslationIntent(message)).toBe(false)
  })
})
