const TRANSLATION_INTENT_PATTERNS = [
  /^翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^帮我翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^我要你翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^请翻译(?:一下|下)?(?:这段|这个|它)?[。！! ]*$/i,
  /^把(?:这段|这个|它)?翻译(?:一下|下)?[。！! ]*$/i,
  /^翻成(?:中文|英文|英语|日文|日语|韩文|韩语|法文|法语|德文|德语)[。！! ]*$/i,
  /^translate(?: this| it| the selection)?[.! ]*$/i,
  /^please translate(?: this| it| the selection)?[.! ]*$/i,
]

/**
 * Fast-path only for explicit translation commands.
 * Ambiguous conversational requests continue through normal AI Chat rather
 * than using fragile keyword matching.
 */
export function isExplicitOverlayTranslationIntent(value: string): boolean {
  const normalized = value.trim()
  return Boolean(normalized) && TRANSLATION_INTENT_PATTERNS.some((pattern) => pattern.test(normalized))
}
