import { useEffect, useRef, useState } from "react"

import { presentOverlay } from "../api/overlay"
import {
  translateTextWithFallback,
  type TranslationProviderMode,
} from "../api/translation"
import type { OverlayStateResponse } from "../api/types"
import {
  resolveTranslationLanguageSwap,
  TRANSLATION_PROVIDER_OPTIONS,
  TRANSLATION_SOURCE_LANGUAGES,
  TRANSLATION_TARGET_LANGUAGES,
  translationProviderLabel,
} from "./translation-workspace-config"

type OverlayTranslationWorkspaceProps = {
  state: OverlayStateResponse
  visible: boolean
}

const TRANSLATION_DEBOUNCE_MS = 420

export default function OverlayTranslationWorkspace({
  state,
  visible,
}: OverlayTranslationWorkspaceProps) {
  const [workingText, setWorkingText] = useState(state.source_text)
  const [translatedText, setTranslatedText] = useState(state.translated_text)
  const [sourceLanguage, setSourceLanguage] = useState(state.source_language || "auto")
  const [targetLanguage, setTargetLanguage] = useState(state.target_language || "zh-CN")
  const [providerMode, setProviderMode] = useState<TranslationProviderMode>("auto")
  const [actualProvider, setActualProvider] = useState(state.provider)
  const [detectedSourceLanguage, setDetectedSourceLanguage] = useState("")
  const [notice, setNotice] = useState(state.translation_notice ?? "")
  const [errorMessage, setErrorMessage] = useState("")
  const [pending, setPending] = useState(false)

  const activeContextRef = useRef(state.context_id)
  const requestSequenceRef = useRef(0)
  const userTouchedRef = useRef(false)
  const immediateRef = useRef(false)

  useEffect(() => {
    if (activeContextRef.current === state.context_id) return

    activeContextRef.current = state.context_id
    requestSequenceRef.current += 1
    userTouchedRef.current = false
    immediateRef.current = false

    setWorkingText(state.source_text)
    setTranslatedText(state.translated_text)
    setSourceLanguage(state.source_language || "auto")
    setTargetLanguage(state.target_language || "zh-CN")
    setProviderMode("auto")
    setActualProvider(state.provider)
    setDetectedSourceLanguage("")
    setNotice(state.translation_notice ?? "")
    setErrorMessage("")
    setPending(false)
  }, [
    state.context_id,
    state.provider,
    state.source_language,
    state.source_text,
    state.target_language,
    state.translated_text,
    state.translation_notice,
  ])

  useEffect(() => {
    if (visible) return
    requestSequenceRef.current += 1
    setPending(false)
  }, [visible])

  useEffect(() => {
    if (!visible || userTouchedRef.current) return
    if (!state.translated_text.trim()) return
    if (workingText !== state.source_text) return

    setTranslatedText(state.translated_text)
    setActualProvider(state.provider)
    setSourceLanguage(state.source_language || "auto")
    setTargetLanguage(state.target_language || "zh-CN")
    setNotice(state.translation_notice ?? "")
    setErrorMessage("")
  }, [
    state.provider,
    state.source_language,
    state.source_text,
    state.target_language,
    state.translated_text,
    state.translation_notice,
    visible,
    workingText,
  ])

  useEffect(() => {
    if (!visible || !userTouchedRef.current) return

    const normalizedSource = workingText.trim()
    if (!normalizedSource) {
      requestSequenceRef.current += 1
      setTranslatedText("")
      setActualProvider("")
      setNotice("")
      setErrorMessage("")
      setPending(false)
      return
    }

    const delay = immediateRef.current ? 0 : TRANSLATION_DEBOUNCE_MS
    immediateRef.current = false

    const timer = window.setTimeout(() => {
      const requestSequence = requestSequenceRef.current + 1
      requestSequenceRef.current = requestSequence
      setPending(true)
      setErrorMessage("")

      void translateTextWithFallback({
        source_text: normalizedSource,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        provider_mode: providerMode,
        request_id: requestSequence,
      })
        .then((result) => {
          if (requestSequenceRef.current !== requestSequence) return
          setTranslatedText(result.translated_text)
          setActualProvider(result.provider)
          setDetectedSourceLanguage(
            result.source_language && result.source_language !== "auto"
              ? result.source_language
              : "",
          )
          setNotice(result.notice)
          setErrorMessage("")

          void presentOverlay({
            context_id: state.context_id,
            source_text: state.source_text,
            translated_text: result.translated_text,
            source_language: result.source_language || sourceLanguage,
            target_language: result.target_language || targetLanguage,
            provider: result.provider === "ai" && result.model
              ? `ai/${result.model}`
              : result.provider,
            translation_notice: result.notice,
            resource_url: state.resource_url,
            resource_title: state.resource_title,
            application: state.application,
            section_heading: state.section_heading,
            context_before: state.context_before,
            context_after: state.context_after,
            source_kind: state.source_kind,
          }).catch(() => undefined)
        })
        .catch((error) => {
          if (requestSequenceRef.current !== requestSequence) return
          setNotice("")
          setErrorMessage(
            error instanceof Error ? error.message : "Translation failed.",
          )
        })
        .finally(() => {
          if (requestSequenceRef.current === requestSequence) {
            setPending(false)
          }
        })
    }, delay)

    return () => window.clearTimeout(timer)
  }, [
    providerMode,
    sourceLanguage,
    state.application,
    state.context_after,
    state.context_before,
    state.context_id,
    state.resource_title,
    state.resource_url,
    state.section_heading,
    state.source_kind,
    state.source_text,
    targetLanguage,
    visible,
    workingText,
  ])

  function markUserChange(immediate = false) {
    requestSequenceRef.current += 1
    userTouchedRef.current = true
    immediateRef.current = immediate
    setPending(false)
  }

  function handleProviderChange(value: TranslationProviderMode) {
    markUserChange(true)
    setProviderMode(value)
  }

  function handleSourceLanguageChange(value: string) {
    markUserChange(true)
    setSourceLanguage(value)
  }

  function handleTargetLanguageChange(value: string) {
    markUserChange(true)
    setTargetLanguage(value)
  }

  function handleSwapLanguages() {
    const swapped = resolveTranslationLanguageSwap(
      sourceLanguage,
      targetLanguage,
      detectedSourceLanguage,
    )
    if (!swapped) return
    markUserChange(true)
    setSourceLanguage(swapped.sourceLanguage)
    setTargetLanguage(swapped.targetLanguage)
  }

  const canSwap = resolveTranslationLanguageSwap(
    sourceLanguage,
    targetLanguage,
    detectedSourceLanguage,
  ) !== null

  return (
    <div
      hidden={!visible}
      className="ait-overlay-translation-workspace shrink-0 border-b border-white/[0.07] bg-black/[0.055] px-3 py-2.5"
      data-ait-selection-scope="internal"
    >
      <div className="flex items-center gap-2">
        <label className="min-w-0 flex-1">
          <span className="sr-only">Translation engine</span>
          <select
            value={providerMode}
            className="ait-overlay-translation-select w-full"
            onChange={(event) => handleProviderChange(event.target.value as TranslationProviderMode)}
          >
            {TRANSLATION_PROVIDER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>

        <label className="min-w-0 flex-1">
          <span className="sr-only">Source language</span>
          <select
            value={sourceLanguage}
            className="ait-overlay-translation-select w-full"
            onChange={(event) => handleSourceLanguageChange(event.target.value)}
          >
            {TRANSLATION_SOURCE_LANGUAGES.map((option) => (
              <option key={option.code} value={option.code}>{option.label}</option>
            ))}
          </select>
        </label>

        <button
          type="button"
          title={canSwap ? "Swap languages" : "Choose a source language before swapping"}
          disabled={!canSwap}
          className="ait-overlay-quiet-button flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs text-slate-400 disabled:opacity-30"
          onClick={handleSwapLanguages}
        >
          ⇄
        </button>

        <label className="min-w-0 flex-1">
          <span className="sr-only">Target language</span>
          <select
            value={targetLanguage}
            className="ait-overlay-translation-select w-full"
            onChange={(event) => handleTargetLanguageChange(event.target.value)}
          >
            {TRANSLATION_TARGET_LANGUAGES.map((option) => (
              <option key={option.code} value={option.code}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-2.5 grid gap-2">
        <section>
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="text-[8px] font-semibold uppercase tracking-[0.14em] text-slate-500">Original</span>
            <span className="text-[8px] text-slate-600">{workingText.length} chars · editable</span>
          </div>
          <textarea
            value={workingText}
            rows={3}
            className="ait-overlay-translation-editor w-full resize-none rounded-[11px] border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-[11px] leading-4 text-slate-200 outline-none focus:border-white/[0.16] focus:bg-white/[0.055]"
            onChange={(event) => {
              markUserChange(false)
              setWorkingText(event.target.value)
            }}
          />
        </section>

        <section className="rounded-[11px] border border-white/[0.07] bg-white/[0.025] px-3 py-2">
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="text-[8px] font-semibold uppercase tracking-[0.14em] text-slate-500">Translation</span>
            <span className="truncate text-[8px] text-slate-600">
              {pending
                ? "Translating…"
                : actualProvider
                  ? translationProviderLabel(actualProvider)
                  : providerMode === "auto"
                    ? "Auto"
                    : translationProviderLabel(providerMode)}
            </span>
          </div>

          {pending && !translatedText ? (
            <div className="ait-overlay-translation-output flex items-center gap-2 text-[10px] text-slate-500">
              <span className="h-3 w-3 animate-spin rounded-full border border-white/20 border-t-white/70" />
              Translating current text…
            </div>
          ) : errorMessage ? (
            <p className="ait-overlay-translation-output whitespace-pre-wrap text-[10px] leading-4 text-rose-200/85">{errorMessage}</p>
          ) : translatedText ? (
            <p className="ait-overlay-translation-output overflow-y-auto whitespace-pre-wrap text-[11px] leading-4 text-slate-200">{translatedText}</p>
          ) : (
            <p className="ait-overlay-translation-output text-[10px] leading-4 text-slate-600">Edit the original text to translate in real time.</p>
          )}
        </section>
      </div>

      {notice && (
        <p className="mt-1.5 truncate text-[8px] leading-3 text-amber-100/65" title={notice}>
          {notice}
        </p>
      )}
    </div>
  )
}
