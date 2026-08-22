export type LanguageOption = readonly [value: string, label: string]

export const sourceLanguages: readonly LanguageOption[] = [
  ["auto", "Auto detect"],
  ["en", "English"],
  ["zh-CN", "Chinese (Simplified)"],
  ["ja", "Japanese"],
  ["ko", "Korean"],
]

export const targetLanguages: readonly LanguageOption[] = [
  ["zh-CN", "Chinese (Simplified)"],
  ["en", "English"],
  ["ja", "Japanese"],
  ["ko", "Korean"],
]
