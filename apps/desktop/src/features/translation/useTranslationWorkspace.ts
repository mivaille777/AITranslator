import { useEffect, useRef, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { getBrowserPage, getBrowserSelection, getBrowserStatus } from "../../api/browser"
import { getHealth } from "../../api/health"
import { showOverlayAssistant } from "../../api/overlay"
import { getReadingSelection, type ReadingSelection } from "../../api/reading"
import {
  getTranslationStatus,
  setTranslationProvider,
  translateText,
  type TranslationProviderName,
} from "../../api/translation"
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
  translationProvider: TranslationProviderName
  providerSwitching: boolean
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
  setTranslationProvider: (value: TranslationProviderName) => void
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
  // Selection capture now opens the AI assistant first. Keep the preference
  // field for settings/backward compatibility, but never let it steal the
  // initial overlay presentation away from Assistant mode.
  const [autoTranslateSelection, setAutoTranslateSelection] = useState(false)
  const lastSelectionId = useRef("")

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

  const providerMutation = useMutation({
    mutationFn: setTranslationProvider,
    onSuccess: () => {
      setTranslation(null)
      setTranslationError("")
      void translationStatusQuery.refetch()
    },
    onError: (error) => {
      setTranslationError(
        error instanceof Error ? error.message : "Unable to switch translation provider.",
      )
    },
  })

  const browserSelection = browserSelectionQuery.data?.selection ?? null
  const browserPage = browserPageQuery.data?.page ?? null
  const readingSelection = readingSelectionQuery.data?.selection ?? null
  const translationProvider: TranslationProviderName =
    translationStatusQuery.data?.provider === "youdao_web" ? "youdao_web" : "google_web"

  useEffect(() => {
    if (!followBrowserSelection || !readingSelection) return
    if (readingSelection.selection_id === lastSelectionId.current) return

    lastSelectionId.current = readingSelection.selection_id
    const nextText = readingSelection.text

    queueMicrotask(() => {
      // A fresh external selection owns the composer seed. Clear any stale
      // translation state, but do not auto-translate or mutate the selection.
      setSourceText(nextText)
      setTranslation(null)
      setTranslationError("")

      void showOverlayAssistant({
        context_id: readingSelection.selection_id,
        source_text: nextText,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        resource_url: readingSelection.resource_url,
        resource_title: readingSelection.resource_title,
        section_heading: readingSelection.section_heading,
        context_before: readingSelection.context_before,
        context_after: readingSelection.context_after,
        source_kind: readingSelection.source_kind,
      }).catch(() => undefined)
    })
  }, [followBrowserSelection, readingSelection, sourceLanguage, targetLanguage])

  const backendState: BackendState = healthQuery.isPending
    ? "checking"
    : healthQuery.isSuccess
      ? "connected"
      : "offline"

  function updateSourceText(value: string) {
    setSourceText(value)
    setTranslationError("")
  }

  function changeTranslationProvider(value: TranslationProviderName) {
    if (value === translationProvider || providerMutation.isPending) return
    setTranslationError("")
    providerMutation.mutate(value)
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
    translationProvider,
    providerSwitching: providerMutation.isPending,
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
    autoTranslating: false,
    manualTranslating: translationMutation.isPending,
    updateSourceText,
    setSourceLanguage,
    setTargetLanguage,
    setTranslationProvider: changeTranslationProvider,
    setFollowBrowserSelection,
    setAutoTranslateSelection,
    translateManual,
    swapLanguages,
    clear,
    useLatestSelection,
  }
}
