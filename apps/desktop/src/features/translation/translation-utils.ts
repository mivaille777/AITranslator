export interface LanguageSwapInput {
  sourceLanguage: string
  targetLanguage: string
  detectedSourceLanguage?: string | null
}

export interface LanguageSwapResult {
  sourceLanguage: string
  targetLanguage: string
}

export function resolveLanguageSwap({
  sourceLanguage,
  targetLanguage,
  detectedSourceLanguage,
}: LanguageSwapInput): LanguageSwapResult {
  const nextTarget = sourceLanguage === "auto"
    ? detectedSourceLanguage && detectedSourceLanguage !== "auto"
      ? detectedSourceLanguage
      : "en"
    : sourceLanguage

  return {
    sourceLanguage: targetLanguage,
    targetLanguage: nextTarget,
  }
}
