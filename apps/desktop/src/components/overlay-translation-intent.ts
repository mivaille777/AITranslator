import { resolveOverlayControlIntent } from "./overlay-interaction-intent"

export interface OverlayTranslationIntent {
  targetLanguage?: string
}

/**
 * Compatibility wrapper for callers/tests that only care about entering
 * translation. The canonical control router lives in overlay-interaction-intent.
 */
export function resolveExplicitOverlayTranslationIntent(
  value: string,
): OverlayTranslationIntent | null {
  const intent = resolveOverlayControlIntent(value, "assistant")
  if (!intent || intent.action !== "enter_translation") return null
  return intent.targetLanguage ? { targetLanguage: intent.targetLanguage } : {}
}

export function isExplicitOverlayTranslationIntent(value: string): boolean {
  return resolveExplicitOverlayTranslationIntent(value) !== null
}
