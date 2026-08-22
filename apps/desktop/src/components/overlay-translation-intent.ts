export interface OverlayTranslationIntent {
  targetLanguage?: string
}

const GENERIC_TRANSLATION_PATTERNS = [
  /^翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^帮我翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^我要你翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^请翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^把(?:这段|这个|它|选中的内容)?翻译(?:一下|下)?[。！! ]*$/i,
  /^(?:请|帮我|我要你|能不能|可以(?:帮我)?)?(?:把)?(?:这段|这个|它|选中的内容)?(?:翻译|译)(?:一下|下)?[吗呢]?[？?。！! ]*$/i,
  /^translate(?: this| it| the selection)?[.! ]*$/i,
  /^please translate(?: this| it| the selection)?[.! ]*$/i,
  /^can you translate(?: this| it| the selection)?[?!. ]*$/i,
]

const TARGET_LANGUAGE_ALIASES: Record<string, string> = {
  英文: "en",
  英语: "en",
  中文: "zh-CN",
  汉语: "zh-CN",
  日文: "ja",
  日语: "ja",
  韩文: "ko",
  韩语: "ko",
  法文: "fr",
  法语: "fr",
  德文: "de",
  德语: "de",
}

const TARGET_LANGUAGE_COMMAND = new RegExp(
  `^(?:请|帮我|我要你|能不能|可以(?:帮我)?)?(?:把)?(?:这段|这个|它|选中的内容)?(?:翻译|翻|译)?(?:一下|下)?(?:成|为)?(${Object.keys(TARGET_LANGUAGE_ALIASES).join("|")})[吗呢]?[？?。！! ]*$`,
  "i",
)

/**
 * Deterministic fast-path for unambiguous translation commands only.
 * Ambiguous conversational requests continue through normal AI Chat.
 */
export function resolveExplicitOverlayTranslationIntent(
  value: string,
): OverlayTranslationIntent | null {
  const normalized = value.trim()
  if (!normalized) return null

  const targetMatch = normalized.match(TARGET_LANGUAGE_COMMAND)
  if (targetMatch) {
    const targetLanguage = TARGET_LANGUAGE_ALIASES[targetMatch[1]]
    if (targetLanguage) return { targetLanguage }
  }
  if (GENERIC_TRANSLATION_PATTERNS.some((pattern) => pattern.test(normalized))) {
    return {}
  }
  return null
}

export function isExplicitOverlayTranslationIntent(value: string): boolean {
  return resolveExplicitOverlayTranslationIntent(value) !== null
}
