import { useEffect, useState, type FormEvent } from "react"

import { API_BASE_URL } from "./api/client"
import { getHealth } from "./api/health"
import { getTranslationStatus, translateText } from "./api/translation"
import type { TranslationResponse } from "./api/types"
import { desktop } from "./desktop"

type BackendState = "checking" | "connected" | "offline"

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
  const [backendState, setBackendState] = useState<BackendState>("checking")
  const [serviceName, setServiceName] = useState("aitrans-backend")
  const [providerName, setProviderName] = useState("Not loaded")
  const [sourceText, setSourceText] = useState("")
  const [sourceLanguage, setSourceLanguage] = useState("auto")
  const [targetLanguage, setTargetLanguage] = useState("zh-CN")
  const [translation, setTranslation] = useState<TranslationResponse | null>(null)
  const [translating, setTranslating] = useState(false)
  const [translationError, setTranslationError] = useState("")

  useEffect(() => {
    let active = true

    async function loadBackendState() {
      try {
        const health = await getHealth()
        if (!active) return
        setServiceName(health.service)
        setBackendState("connected")

        try {
          const status = await getTranslationStatus()
          if (!active) return
          setProviderName(status.provider)
          setSourceLanguage(status.source_language)
          setTargetLanguage(status.target_language)
        } catch {
          if (active) setProviderName("Unavailable")
        }
      } catch {
        if (active) setBackendState("offline")
      }
    }

    void loadBackendState()
    return () => {
      active = false
    }
  }, [])

  async function handleTranslate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!sourceText.trim()) {
      setTranslationError("Enter some text before translating.")
      return
    }

    setTranslating(true)
    setTranslationError("")
    try {
      const result = await translateText({
        source_text: sourceText,
        source_language: sourceLanguage,
        target_language: targetLanguage,
      })
      setTranslation(result)
    } catch (error) {
      setTranslation(null)
      setTranslationError(error instanceof Error ? error.message : "Translation failed.")
    } finally {
      setTranslating(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-10 text-slate-950">
      <div className="mx-auto w-full max-w-5xl">
        <header className="rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                Stage 2 · Translation Core
              </p>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight">
                AITranslator WebReBuild
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                The first real business path now runs from React through FastAPI into the existing deterministic translation core.
              </p>
            </div>

            <div className="grid min-w-72 gap-2 text-sm">
              <StatusRow label="Runtime" value={desktop.runtime} />
              <StatusRow
                label="Backend"
                value={
                  backendState === "checking"
                    ? "Checking…"
                    : backendState === "connected"
                      ? `${serviceName} · Connected`
                      : `Offline · ${API_BASE_URL}`
                }
              />
              <StatusRow label="Provider" value={providerName} />
            </div>
          </div>
        </header>

        <section className="mt-6 grid gap-6 lg:grid-cols-2">
          <form
            className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
            onSubmit={handleTranslate}
          >
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Source</h2>
                <p className="mt-1 text-sm text-slate-500">Normal translation stays outside LangGraph.</p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                Deterministic path
              </span>
            </div>

            <textarea
              className="mt-5 min-h-56 w-full resize-y rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 outline-none transition focus:border-slate-400 focus:bg-white"
              placeholder="Enter text to translate…"
              value={sourceText}
              onChange={(event) => setSourceText(event.target.value)}
            />

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <LanguageSelect
                label="Source language"
                value={sourceLanguage}
                options={sourceLanguages}
                onChange={setSourceLanguage}
              />
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
              disabled={backendState !== "connected" || translating}
            >
              {translating ? "Translating…" : "Translate"}
            </button>
          </form>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Translation</h2>
                <p className="mt-1 text-sm text-slate-500">FastAPI → TranslationService → TranslationManager</p>
              </div>
              {translation && (
                <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                  {translation.provider}
                </span>
              )}
            </div>

            <div className="mt-5 min-h-56 rounded-xl border border-slate-200 bg-slate-50 p-4">
              {translation ? (
                <p className="whitespace-pre-wrap text-sm leading-7 text-slate-900">
                  {translation.translated_text}
                </p>
              ) : (
                <p className="text-sm leading-6 text-slate-400">
                  The translated text will appear here after the backend completes the request.
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

type LanguageOption = readonly [value: string, label: string]

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
