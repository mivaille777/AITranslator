import { useCallback, useEffect, useRef, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { getBrowserPage, getBrowserSelection, getBrowserStatus } from "../../api/browser"
import { getHealth } from "../../api/health"
import { presentOverlay, showOverlayError, showOverlayLoading } from "../../api/overlay"
import { getTranslationStatus, translateText } from "../../api/translation"
import type {
  BrowserBridgeStatusResponse,
  BrowserPage,
  BrowserSelection,
  TranslationResponse,
} from "../../api/types"
import { resolveLanguageSwap } from "./translation-utils"

export type BackendState = "checking" | "connected" | "offline"

export interface TranslationWorkspaceController {
  backendState: BackendState
  backendService: string
  providerName: string
  browserStatus: BrowserBridgeStatusResponse | undefined
  browserStatusChecking: boolean
  browserSelection: BrowserSelection | null
  browserPage: BrowserPage | null
  sourceText: string
  sourceLanguage: string
  targetLanguage: string
  translation: TranslationResponse | null
  translationError: string
  followBrowserSelection: boolean
  autoTranslateSelection: boolean
  autoTranslating: boolean
  manualTranslating: boolean
  updateSourceText: (value: string) => void
  setSourceLanguage: (value: string) => void
  setTargetLanguage: (value: string) => void
  setFollowBrowserSelection: (checked: boolean) => void
  setAutoTranslateSelection: (checked: boolean) => void
  translateManual: () => void
  swapLanguages: () => void
  clear: () => void
  useLatestSelection: () => void
}

export function useTranslationWorkspace(): TranslationWorkspaceController {
  const [sourceText, setSourceText] = useState("")
  const [sourceLanguage, setSourceLanguage] = useState("auto")
  const [targetLanguage, setTargetLanguage] = useState("zh-CN")
  const [translation, setTranslation] = useState<TranslationResponse | null>(null)
  const [translationError, setTranslationError] = useState("")
  const [followBrowserSelection, setFollowBrowserSelection] = useState(true)
  const [autoTranslateSelection, setAutoTranslateSelection] = useState(true)
  const [autoTranslating, setAutoTranslating] = useState(false)
  const lastSelectionId = useRef("")
  const lastAutoSelectionId = useRef("")

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 5_000,
  })

  const translationStatusQuery = useQuery({
    queryKey: ["translation-status"],
    queryFn: getTranslationStatus,
    enabled: healthQuery.isSuccess,
    refetchInterval: 15_000,
  })

  const browserStatusQuery = useQuery({
    queryKey: ["browser-status"],
    queryFn: getBrowserStatus,
    enabled: healthQuery.isSuccess,
    refetchInterval: 2_000,
  })

  const browserSelectionQuery = useQuery({
    queryKey: ["browser-selection"],
    queryFn: getBrowserSelection,
    enabled: healthQuery.isSuccess,
    refetchInterval: 500,
  })

  const browserPageQuery = useQuery({
    queryKey: ["browser-page"],
    queryFn: getBrowserPage,
    enabled: healthQuery.isSuccess,
    refetchInterval: 2_000,
  })

  const translationMutation = useMutation({
    mutationFn: translateText,
    onSuccess: (result) => {
      setTranslation(result)
      setTranslationError("")
    },
    onError: (error) => {
      setTranslation(null)
      setTranslationError(error instanceof Error ? error.message : "Translation failed.")
    },
  })

  const browserSelection = browserSelectionQuery.data?.selection ?? null
  const browserPage = browserPageQuery.data?.page ?? null

  const translateBrowserSelection = useCallback(
    async (selection: BrowserSelection) => {
      const contextId = selection.selection_id
      lastAutoSelectionId.current = contextId
      setAutoTranslating(true)

      void showOverlayLoading({
        context_id: contextId,
        source_text: selection.text,
        source_language: sourceLanguage,
        target_language: targetLanguage,
      }).catch(() => undefined)

      try {
        const result = await translateText({
          source_text: selection.text,
          source_language: sourceLanguage,
          target_language: targetLanguage,
        })
        if (lastAutoSelectionId.current !== contextId) return

        setTranslation(result)
        setTranslationError("")
        void presentOverlay({
          context_id: contextId,
          source_text: result.source_text,
          translated_text: result.translated_text,
          source_language: result.source_language,
          target_language: result.target_language,
          provider: result.provider,
        }).catch(() => undefined)
      } catch (error) {
        if (lastAutoSelectionId.current !== contextId) return

        const message = error instanceof Error ? error.message : "Translation failed."
        setTranslation(null)
        setTranslationError(message)
        void showOverlayError({
          context_id: contextId,
          source_text: selection.text,
          source_language: sourceLanguage,
          target_language: targetLanguage,
          message,
        }).catch(() => undefined)
      } finally {
        if (lastAutoSelectionId.current === contextId) {
          setAutoTranslating(false)
        }
      }
    },
    [sourceLanguage, targetLanguage],
  )

  useEffect(() => {
    if (!followBrowserSelection || !browserSelection) return
    if (browserSelection.selection_id === lastSelectionId.current) return

    lastSelectionId.current = browserSelection.selection_id
    queueMicrotask(() => {
      setSourceText(browserSelection.text)
      setTranslation(null)
      setTranslationError("")
      if (autoTranslateSelection) {
        void translateBrowserSelection(browserSelection)
      }
    })
  }, [
    autoTranslateSelection,
    browserSelection,
    followBrowserSelection,
    translateBrowserSelection,
  ])

  const backendState: BackendState = healthQuery.isPending
    ? "checking"
    : healthQuery.isSuccess
      ? "connected"
      : "offline"

  function updateSourceText(value: string) {
    setSourceText(value)
    setTranslationError("")
  }

  function translateManual() {
    if (!sourceText.trim()) {
      setTranslationError("Enter or capture some text before translating.")
      return
    }

    setTranslationError("")
    translationMutation.mutate({
      source_text: sourceText,
      source_language: sourceLanguage,
      target_language: targetLanguage,
    })
  }

  function swapLanguages() {
    const next = resolveLanguageSwap({
      sourceLanguage,
      targetLanguage,
      detectedSourceLanguage: translation?.source_language,
    })
    setSourceLanguage(next.sourceLanguage)
    setTargetLanguage(next.targetLanguage)

    if (translation) {
      setSourceText(translation.translated_text)
      setTranslation(null)
      setTranslationError("")
    }
  }

  function clear() {
    setSourceText("")
    setTranslation(null)
    setTranslationError("")
    lastSelectionId.current = browserSelection?.selection_id ?? ""
    lastAutoSelectionId.current = ""
    setAutoTranslating(false)
  }

  function useLatestSelection() {
    if (!browserSelection) return
    setSourceText(browserSelection.text)
    setTranslation(null)
    setTranslationError("")
  }

  return {
    backendState,
    backendService: healthQuery.data?.service ?? "aitrans-backend",
    providerName: translationStatusQuery.data?.provider ?? "Not loaded",
    browserStatus: browserStatusQuery.data,
    browserStatusChecking: browserStatusQuery.isPending,
    browserSelection,
    browserPage,
    sourceText,
    sourceLanguage,
    targetLanguage,
    translation,
    translationError,
    followBrowserSelection,
    autoTranslateSelection,
    autoTranslating,
    manualTranslating: translationMutation.isPending,
    updateSourceText,
    setSourceLanguage,
    setTargetLanguage,
    setFollowBrowserSelection,
    setAutoTranslateSelection,
    translateManual,
    swapLanguages,
    clear,
    useLatestSelection,
  }
}
