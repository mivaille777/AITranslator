import type { TranslationProviderMode } from "../api/translation"

export type TranslationLanguageOption = {
  code: string
  label: string
}

export const TRANSLATION_PROVIDER_OPTIONS: Array<{
  value: TranslationProviderMode
  label: string
}> = [
  { value: "auto", label: "Auto" },
  { value: "youdao_web", label: "Youdao" },
  { value: "google_web", label: "Google" },
  { value: "ai", label: "AI" },
]

export const TRANSLATION_SOURCE_LANGUAGES: TranslationLanguageOption[] = [
  { code: "auto", label: "Auto detect" },
  { code: "zh-CN", label: "中文" },
  { code: "en", label: "English" },
  { code: "ja", label: "日本語" },
  { code: "ko", label: "한국어" },
  { code: "fr", label: "Français" },
  { code: "de", label: "Deutsch" },
  { code: "es", label: "Español" },
  { code: "ru", label: "Русский" },
]

export const TRANSLATION_TARGET_LANGUAGES = TRANSLATION_SOURCE_LANGUAGES.filter(
  (item) => item.code !== "auto",
)

export function translationProviderLabel(provider: string): string {
  if (provider === "youdao_web") return "Youdao"
  if (provider === "google_web") return "Google"
  if (provider === "ai" || provider.startsWith("ai/")) return "AI"
  return provider || "Unknown"
}

function looksChinese(text: string): boolean {
  const normalized = text.replace(/\s+/g, "")
  if (!normalized) return false
  const hanCount = (normalized.match(/[\u3400-\u9fff]/g) ?? []).length
  return hanCount >= Math.max(2, Math.ceil(normalized.length * 0.2))
}

/**
 * Avoid a no-op first translation when the captured text is already in the
 * configured target language. Explicit user target commands bypass this helper.
 */
export function resolvePreferredTranslationTarget(
  sourceText: string,
  sourceLanguage: string,
  targetLanguage: string,
): string {
  const source = sourceLanguage.trim() || "auto"
  const target = targetLanguage.trim() || "zh-CN"

  if (source !== "auto") {
    if (source !== target) return target
    return source === "zh-CN" ? "en" : "zh-CN"
  }

  if (target === "zh-CN" && looksChinese(sourceText)) return "en"
  if (target === "en" && !looksChinese(sourceText)) return "zh-CN"
  return target
}

export function resolveTranslationLanguageSwap(
  sourceLanguage: string,
  targetLanguage: string,
  detectedSourceLanguage = "",
): { sourceLanguage: string; targetLanguage: string } | null {
  const effectiveSource = sourceLanguage === "auto"
    ? detectedSourceLanguage.trim()
    : sourceLanguage
  if (!effectiveSource || effectiveSource === "auto") return null
  return {
    sourceLanguage: targetLanguage,
    targetLanguage: effectiveSource,
  }
}
