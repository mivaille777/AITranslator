import { useCallback, useEffect, useRef, useState, type FormEvent } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { getBrowserPage, getBrowserSelection, getBrowserStatus } from "./api/browser"
import { API_BASE_URL } from "./api/client"
import { getHealth } from "./api/health"
import { presentOverlay, showOverlayError, showOverlayLoading } from "./api/overlay"
import { getTranslationStatus, translateText } from "./api/translation"
import type { BrowserSelection, TranslationResponse } from "./api/types"
import OverlayPreferencesPanel from "./components/OverlayPreferencesPanel"
import { desktop } from "./desktop"

type BackendState = "checking" | "connected" | "offline"
type LanguageOption = readonly [value: string, label: string]

const sourceLanguages = [
  ["auto", "Auto detect"],
  ["en", "English"],
  ["zh-CN", "Chinese (Simplified)"],
  ["ja", "Japanese"],
  ["ko", "Korean"],
] as const

const targetLanguages = [
  ["zh-CN", "Chinese (Simplified)"],
  ["en", "English"],
  ["ja", "Japanese"],
  ["ko", "Korean"],
] as const

function App() {
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
    setSourceText(browserSelection.text)
    setTranslation(null)
    setTranslationError("")

    if (!autoTranslateSelection) return
    queueMicrotask(() => {
      void translateBrowserSelection(browserSelection)
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

  const providerName = translationStatusQuery.data?.provider ?? "Not loaded"
  const browserStatus = browserStatusQuery.data

  function handleTranslate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
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

  function handleSwapLanguages() {
    const detectedSource = translation?.source_language
    const nextSource = sourceLanguage === "auto"
      ? detectedSource && detectedSource !== "auto"
        ? detectedSource
        : "en"
      : sourceLanguage

    setSourceLanguage(targetLanguage)
    setTargetLanguage(nextSource)

    if (translation) {
      setSourceText(translation.translated_text)
      setTranslation(null)
      setTranslationError("")
    }
  }

  function handleClear() {
    setSourceText("")
    setTranslation(null)
    setTranslationError("")
    lastSelectionId.current = browserSelection?.selection_id ?? ""
    lastAutoSelectionId.current = ""
    setAutoTranslating(false)
  }

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-8 text-slate-950">
      <div className="mx-auto w-full max-w-6xl">
        <header className="rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                Stage 2 · Interactive Translation Overlay
              </p>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight">
                AITranslator WebReBuild
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                Browser selection now drives a monitor-aware Tauri overlay with configurable placement and interaction behavior.
              </p>
            </div>

            <div className="grid min-w-80 gap-2 text-sm">
              <StatusRow label="Runtime" value={desktop.runtime} />
              <StatusRow
                label="Backend"
                value={
                  backendState === "checking"
                    ? "Checking…"
                    : backendState === "connected"
                      ? `${healthQuery.data?.service ?? "aitrans-backend"} · Connected`
                      : `Offline · ${API_BASE_URL}`
                }
              />
              <StatusRow label="Provider" value={providerName} />
              <StatusRow
                label="Browser bridge"
                value={
                  browserStatus?.running
                    ? `Listening · ${browserStatus.port}`
                    : browserStatusQuery.isPending
                      ? "Checking…"
                      : "Unavailable / port busy"
                }
              />
            </div>
          </div>
        </header>

        <OverlayPreferencesPanel />

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold">Browser Reading Context</h2>
                <span className={`h-2 w-2 rounded-full ${browserStatus?.has_extension_activity ? "bg-emerald-500" : "bg-slate-300"}`} />
              </div>
              <p className="mt-1 truncate text-sm text-slate-500">
                {browserPage?.title || browserSelection?.title || "Waiting for the browser extension…"}
              </p>
              {(browserPage?.url || browserSelection?.url) && (
                <p className="mt-1 truncate text-xs text-slate-400">
                  {browserPage?.url || browserSelection?.url}
                </p>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <Toggle
                label="Follow selection"
                checked={followBrowserSelection}
                onChange={setFollowBrowserSelection}
              />
              <Toggle
                label={autoTranslating ? "Auto translating…" : "Auto translate + overlay"}
                checked={autoTranslateSelection}
                onChange={setAutoTranslateSelection}
              />
            </div>
          </div>

          {(browserSelection?.heading || browserPage?.heading) && (
            <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
              Section: <strong className="font-medium text-slate-700">{browserSelection?.heading || browserPage?.heading}</strong>
            </p>
          )}
        </section>

        <section className="mt-6 grid gap-6 lg:grid-cols-2">
          <form
            className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
            onSubmit={handleTranslate}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Source</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Select text in the browser or enter it manually.
                </p>
              </div>
              <button
                type="button"
                className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
                onClick={handleClear}
              >
                Clear
              </button>
            </div>

            <textarea
              className="mt-5 min-h-64 w-full resize-y rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 outline-none transition focus:border-slate-400 focus:bg-white"
              placeholder="Enter text to translate, or select text in Chrome/Edge…"
              value={sourceText}
              onChange={(event) => {
                setSourceText(event.target.value)
                setTranslationError("")
              }}
            />

            {browserSelection && (
              <div className="mt-3 flex items-center justify-between gap-3 text-xs text-slate-500">
                <span className="truncate">Latest browser selection · {browserSelection.text.length} chars</span>
                {!followBrowserSelection && (
                  <button
                    type="button"
                    className="shrink-0 font-medium text-slate-800 hover:underline"
                    onClick={() => setSourceText(browserSelection.text)}
                  >
                    Use selection
                  </button>
                )}
              </div>
            )}

            <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-end gap-2">
              <LanguageSelect
                label="Source language"
                value={sourceLanguage}
                options={sourceLanguages}
                onChange={setSourceLanguage}
              />
              <button
                type="button"
                className="mb-0.5 rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-600 hover:bg-slate-50"
                onClick={handleSwapLanguages}
                title="Swap languages"
              >
                ⇄
              </button>
              <LanguageSelect
                label="Target language"
                value={targetLanguage}
                options={targetLanguages}
                onChange={setTargetLanguage}
              />
            </div>

            {translationError && (
              <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {translationError}
              </p>
            )}

            <button
              className="mt-5 w-full rounded-xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
              type="submit"
              disabled={backendState !== "connected" || translationMutation.isPending}
            >
              {translationMutation.isPending ? "Translating…" : "Translate"}
            </button>
          </form>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Translation</h2>
                <p className="mt-1 text-sm text-slate-500">
                  FastAPI → TranslationService → TranslationManager
                </p>
              </div>
              {translation && (
                <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                  {translation.provider}
                </span>
              )}
            </div>

            <div className="mt-5 min-h-64 rounded-xl border border-slate-200 bg-slate-50 p-4">
              {translation ? (
                <p className="whitespace-pre-wrap text-sm leading-7 text-slate-900">
                  {translation.translated_text}
                </p>
              ) : (
                <p className="text-sm leading-6 text-slate-400">
                  {autoTranslating
                    ? "The current browser selection is being translated…"
                    : "The translated text will appear here after the backend completes the request."}
                </p>
              )}
            </div>

            <dl className="mt-4 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
              <div className="rounded-lg bg-slate-50 px-3 py-2">
                Detected source: <strong className="font-medium text-slate-700">{translation?.source_language ?? "—"}</strong>
              </div>
              <div className="rounded-lg bg-slate-50 px-3 py-2">
                Target: <strong className="font-medium text-slate-700">{translation?.target_language ?? targetLanguage}</strong>
              </div>
            </dl>

            {(browserSelection?.context_before || browserSelection?.context_after) && (
              <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Nearby context</p>
                <p className="mt-2 line-clamp-4 text-xs leading-5 text-slate-500">
                  {[browserSelection.context_before, browserSelection.text, browserSelection.context_after]
                    .filter(Boolean)
                    .join(" ")}
                </p>
              </div>
            )}
          </section>
        </section>
      </div>
    </main>
  )
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-5 rounded-lg bg-slate-50 px-4 py-2.5">
      <span className="text-slate-500">{label}</span>
      <span className="max-w-52 truncate font-medium capitalize text-slate-900">{value}</span>
    </div>
  )
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="flex items-center gap-2 rounded-xl bg-slate-50 px-4 py-2.5 text-sm text-slate-700">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  )
}

function LanguageSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: readonly LanguageOption[]
  onChange: (value: string) => void
}) {
  return (
    <label className="grid gap-1.5 text-xs font-medium text-slate-600">
      {label}
      <select
        className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-slate-400"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  )
}

export default App
