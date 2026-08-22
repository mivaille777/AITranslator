export interface OverlayTranslationIntent {
  targetLanguage?: string
}

const GENERIC_TRANSLATION_PATTERNS = [
  /^翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^帮我翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^我要你翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^请翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^把(?:这段|这个|它)?翻译(?:一下|下)?[。！! ]*$/i,
  /^translate(?: this| it| the selection)?[.! ]*$/i,
  /^please translate(?: this| it| the selection)?[.! ]*$/i,
]

const TARGET_LANGUAGE_PATTERNS: Array<[RegExp, string]> = [
  [/^翻成(?:英文|英语)[。！! ]*$/i, "en"],
  [/^翻成(?:中文|汉语)[。！! ]*$/i, "zh-CN"],
  [/^翻成(?:日文|日语)[。！! ]*$/i, "ja"],
  [/^翻成(?:韩文|韩语)[。！! ]*$/i, "ko"],
  [/^翻成(?:法文|法语)[。！! ]*$/i, "fr"],
  [/^翻成(?:德文|德语)[。！! ]*$/i, "de"],
]

/**
 * Deterministic fast-path for unambiguous translation commands only.
 * Ambiguous conversational requests continue through normal AI Chat.
 */
export function resolveExplicitOverlayTranslationIntent(
  value: string,
): OverlayTranslationIntent | null {
  const normalized = value.trim()
  if (!normalized) return null

  for (const [pattern, targetLanguage] of TARGET_LANGUAGE_PATTERNS) {
    if (pattern.test(normalized)) return { targetLanguage }
  }
  if (GENERIC_TRANSLATION_PATTERNS.some((pattern) => pattern.test(normalized))) {
    return {}
  }
  return null
}

export function isExplicitOverlayTranslationIntent(value: string): boolean {
  return resolveExplicitOverlayTranslationIntent(value) !== null
}
