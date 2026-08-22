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
  if (provider === "ai") return "AI"
  return provider || "Unknown"
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
