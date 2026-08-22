import { useEffect, useRef, useState } from "react"

import { presentOverlay } from "../api/overlay"
import {
  translateTextWithFallback,
  type TranslationProviderMode,
} from "../api/translation"
import type { OverlayStateResponse } from "../api/types"

const DEBOUNCE_MS = 420

const LANGUAGE_OPTIONS = [
  { value: "auto", label: "Auto detect", sourceOnly: true },
  { value: "zh-CN", label: "Chinese" },
  { value: "en", label: "English" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
]

const PROVIDER_OPTIONS: Array<{ value: TranslationProviderMode; label: string }> = [
  { value: "auto", label: "Auto" },
  { value: "youdao_web", label: "Youdao" },
  { value: "google_web", label: "Google" },
  { value: "ai", label: "AI" },
]

type CachedWorkspace = {
  sourceText: string
  sourceLanguage: string
  targetLanguage: string
  providerMode: TranslationProviderMode
}

const workspaceCache = new Map<string, CachedWorkspace>()

function providerDisplayName(provider: string, model = ""): string {
  if (provider === "youdao_web") return "Youdao"
  if (provider === "google_web") return "Google"
  if (provider === "ai" || provider.startsWith("ai/")) return model ? `AI · ${model}` : "AI"
  return provider || "Translation"
}

function initialWorkspace(state: OverlayStateResponse): CachedWorkspace {
  return workspaceCache.get(state.context_id) ?? {
    sourceText: state.source_text,
    sourceLanguage: state.source_language || "auto",
    targetLanguage: state.target_language || "zh-CN",
    providerMode: "auto",
  }
}

export default function OverlayTranslationWorkspace({ state }: { state: OverlayStateResponse }) {
  const initialRef = useRef<CachedWorkspace | null>(null)
  if (initialRef.current === null) initialRef.current = initialWorkspace(state)
  const initial = initialRef.current

  const [sourceText, setSourceText] = useState(initial.sourceText)
  const [sourceLanguage, setSourceLanguage] = useState(initial.sourceLanguage)
  const [targetLanguage, setTargetLanguage] = useState(initial.targetLanguage)
  const [providerMode, setProviderMode] = useState<TranslationProviderMode>(initial.providerMode)
  const [translatedText, setTranslatedText] = useState(state.translated_text)
  const [providerLabel, setProviderLabel] = useState(providerDisplayName(state.provider))
  const [notice, setNotice] = useState(state.translation_notice?.trim() ?? "")
  const [errorMessage, setErrorMessage] = useState("")
  const [busy, setBusy] = useState(false)
  const latestRequestRef = useRef(0)
  const lastCompletedSignatureRef = useRef(
    state.translated_text.trim()
      ? `${initial.sourceText}\u001f${initial.sourceLanguage}\u001f${initial.targetLanguage}\u001f${initial.providerMode}`
      : "",
  )

  useEffect(() => {
    workspaceCache.set(state.context_id, {
      sourceText,
      sourceLanguage,
      targetLanguage,
      providerMode,
    })
  }, [providerMode, sourceLanguage, sourceText, state.context_id, targetLanguage])

  useEffect(() => {
    const signature = `${sourceText}\u001f${sourceLanguage}\u001f${targetLanguage}\u001f${providerMode}`
    const normalizedSource = sourceText.trim()

    // Every edit/settings change immediately invalidates older in-flight work.
    const requestId = latestRequestRef.current + 1
    latestRequestRef.current = requestId

    if (!normalizedSource) {
      setBusy(false)
      setTranslatedText("")
      setNotice("")
      setErrorMessage("")
      return
    }
    if (signature === lastCompletedSignatureRef.current) return

    const timer = window.setTimeout(() => {
      setBusy(true)
      setErrorMessage("")

      void translateTextWithFallback({
        source_text: sourceText,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        provider_mode: providerMode,
        request_id: requestId,
      }).then(async (result) => {
        if (latestRequestRef.current !== requestId) return
        lastCompletedSignatureRef.current = signature
        setTranslatedText(result.translated_text)
        setProviderLabel(providerDisplayName(result.provider, result.model))
        setNotice(result.notice)
        setErrorMessage("")

        // The editable translation source is a working copy. Persist only the
        // result/settings while preserving the original captured reading text.
        await presentOverlay({
          context_id: state.context_id,
          source_text: state.source_text,
          translated_text: result.translated_text,
          source_language: sourceLanguage,
          target_language: targetLanguage,
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
      }).catch((error) => {
        if (latestRequestRef.current !== requestId) return
        setErrorMessage(error instanceof Error ? error.message : "Translation failed.")
      }).finally(() => {
        if (latestRequestRef.current === requestId) setBusy(false)
      })
    }, DEBOUNCE_MS)

    return () => window.clearTimeout(timer)
  }, [providerMode, sourceLanguage, sourceText, state, targetLanguage])

  const canSwap = sourceLanguage !== "auto"

  return (
    <div
      className="ait-overlay-translation-workspace border-b border-white/[0.07] bg-black/[0.06] px-3 py-3"
      data-ait-selection-scope="internal"
    >
      <div className="flex items-center gap-2">
        <label className="min-w-0 flex-1">
          <span className="sr-only">Translation engine</span>
          <select
            value={providerMode}
            className="ait-overlay-select w-full rounded-lg border border-white/[0.08] bg-white/[0.045] px-2 py-1.5 text-[10px] text-slate-300 outline-none"
            onChange={(event) => setProviderMode(event.target.value as TranslationProviderMode)}
          >
            {PROVIDER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>

        <label className="min-w-0 flex-1">
          <span className="sr-only">Source language</span>
          <select
            value={sourceLanguage}
            className="ait-overlay-select w-full rounded-lg border border-white/[0.08] bg-white/[0.045] px-2 py-1.5 text-[10px] text-slate-300 outline-none"
            onChange={(event) => setSourceLanguage(event.target.value)}
          >
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>

        <button
          type="button"
          disabled={!canSwap}
          title={canSwap ? "Swap source and target languages" : "Choose a source language before swapping"}
          className="ait-overlay-quiet-button flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs text-slate-400 disabled:opacity-30"
          onClick={() => {
            if (!canSwap) return
            const previousSource = sourceLanguage
            setSourceLanguage(targetLanguage)
            setTargetLanguage(previousSource)
          }}
        >
          ⇄
        </button>

        <label className="min-w-0 flex-1">
          <span className="sr-only">Target language</span>
          <select
            value={targetLanguage}
            className="ait-overlay-select w-full rounded-lg border border-white/[0.08] bg-white/[0.045] px-2 py-1.5 text-[10px] text-slate-300 outline-none"
            onChange={(event) => setTargetLanguage(event.target.value)}
          >
            {LANGUAGE_OPTIONS.filter((option) => !option.sourceOnly).map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-2 grid gap-2">
        <label>
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">Original</span>
            <span className="text-[9px] text-slate-600">editable · live</span>
          </div>
          <textarea
            value={sourceText}
            rows={3}
            className="max-h-28 min-h-16 w-full resize-y rounded-[12px] border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-[11px] leading-4 text-slate-200 outline-none focus:border-white/[0.16]"
            onChange={(event) => setSourceText(event.target.value)}
          />
        </label>

        <div>
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">Translation</span>
            <span className="flex items-center gap-1.5 text-[9px] text-slate-600">
              {busy && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-300" />}
              {busy ? "Translating…" : providerLabel}
            </span>
          </div>
          <div className="max-h-28 min-h-16 overflow-y-auto rounded-[12px] border border-white/[0.07] bg-white/[0.025] px-3 py-2 text-[11px] leading-4 text-slate-200">
            {translatedText ? (
              <p className="whitespace-pre-wrap">{translatedText}</p>
            ) : busy ? (
              <p className="text-slate-500">Translating…</p>
            ) : (
              <p className="text-slate-600">Translation will appear here.</p>
            )}
          </div>
        </div>
      </div>

      {notice && !errorMessage && (
        <p className="mt-2 text-[9px] leading-4 text-amber-200/75">{notice}</p>
      )}
      {errorMessage && (
        <p className="mt-2 text-[9px] leading-4 text-rose-200/85">{errorMessage}</p>
      )}
    </div>
  )
}
