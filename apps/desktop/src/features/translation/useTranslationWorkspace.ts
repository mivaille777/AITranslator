import { useCallback, useEffect, useRef, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { getBrowserPage, getBrowserSelection, getBrowserStatus } from "../../api/browser"
import { getHealth } from "../../api/health"
import { presentOverlay, showOverlayError, showOverlayLoading } from "../../api/overlay"
import { getReadingSelection, type ReadingSelection } from "../../api/reading"
import { getTranslationStatus, translateText } from "../../api/translation"
import type {
  BrowserBridgeStatusResponse,
  BrowserPage,
  BrowserSelection,
  TranslationResponse,
} from "../../api/types"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"
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
  readingSelection: ReadingSelection | null
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
    queryKey: queryKeys.health,
    queryFn: getHealth,
    refetchInterval: queryPolling.health,
  })

  const translationStatusQuery = useQuery({
    queryKey: queryKeys.translation.status,
    queryFn: getTranslationStatus,
    enabled: healthQuery.isSuccess,
    refetchInterval: queryPolling.translationStatus,
  })

  const browserStatusQuery = useQuery({
    queryKey: queryKeys.browser.status,
    queryFn: getBrowserStatus,
    enabled: healthQuery.isSuccess,
    refetchInterval: queryPolling.browserStatus,
  })

  const browserSelectionQuery = useQuery({
    queryKey: queryKeys.browser.selection,
    queryFn: getBrowserSelection,
    enabled: healthQuery.isSuccess,
    refetchInterval: queryPolling.browserSelection,
  })

  const browserPageQuery = useQuery({
    queryKey: queryKeys.browser.page,
    queryFn: getBrowserPage,
    enabled: healthQuery.isSuccess,
    refetchInterval: queryPolling.browserPage,
  })

  const readingSelectionQuery = useQuery({
    queryKey: queryKeys.reading.selection,
    queryFn: getReadingSelection,
    enabled: healthQuery.isSuccess,
    refetchInterval: queryPolling.readingSelection,
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
  const readingSelection = readingSelectionQuery.data?.selection ?? null

  const translateReadingSelection = useCallback(
    async (selection: ReadingSelection) => {
      const contextId = selection.selection_id
      lastAutoSelectionId.current = contextId
      setAutoTranslating(true)
      const readingContext = {
        resource_url: selection.resource_url,
        resource_title: selection.resource_title,
        section_heading: selection.section_heading,
        context_before: selection.context_before,
        context_after: selection.context_after,
        source_kind: selection.source_kind,
      }

      void showOverlayLoading({
        context_id: contextId,
        source_text: selection.text,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        ...readingContext,
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
          ...readingContext,
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
          ...readingContext,
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
    if (!followBrowserSelection || !readingSelection) return
    if (readingSelection.selection_id === lastSelectionId.current) return

    lastSelectionId.current = readingSelection.selection_id
    queueMicrotask(() => {
      setSourceText(readingSelection.text)
      setTranslation(null)
      setTranslationError("")
      if (autoTranslateSelection) {
        void translateReadingSelection(readingSelection)
      }
    })
  }, [
    autoTranslateSelection,
    followBrowserSelection,
    readingSelection,
    translateReadingSelection,
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
    lastSelectionId.current = readingSelection?.selection_id ?? ""
    lastAutoSelectionId.current = ""
    setAutoTranslating(false)
  }

  function useLatestSelection() {
    if (!readingSelection) return
    setSourceText(readingSelection.text)
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
    readingSelection,
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
