import type { FormEvent } from "react"

import { LanguageSelect } from "../../shared/components/LanguageSelect"
import { sourceLanguages, targetLanguages } from "./languages"
import type { TranslationWorkspaceController } from "./useTranslationWorkspace"

export default function TranslationWorkspace({
  workspace,
}: {
  workspace: TranslationWorkspaceController
}) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    workspace.translateManual()
  }

  return (
    <section className="mt-6 grid gap-6 lg:grid-cols-2">
      <form
        className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
        onSubmit={handleSubmit}
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
            onClick={workspace.clear}
          >
            Clear
          </button>
        </div>

        <textarea
          className="mt-5 min-h-64 w-full resize-y rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 outline-none transition focus:border-slate-400 focus:bg-white"
          placeholder="Enter text to translate, or select text in Chrome/Edge…"
          value={workspace.sourceText}
          onChange={(event) => workspace.updateSourceText(event.target.value)}
        />

        {workspace.browserSelection && (
          <div className="mt-3 flex items-center justify-between gap-3 text-xs text-slate-500">
            <span className="truncate">
              Latest browser selection · {workspace.browserSelection.text.length} chars
            </span>
            {!workspace.followBrowserSelection && (
              <button
                type="button"
                className="shrink-0 font-medium text-slate-800 hover:underline"
                onClick={workspace.useLatestSelection}
              >
                Use selection
              </button>
            )}
          </div>
        )}

        <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-end gap-2">
          <LanguageSelect
            label="Source language"
            value={workspace.sourceLanguage}
            options={sourceLanguages}
            onChange={workspace.setSourceLanguage}
          />
          <button
            type="button"
            className="mb-0.5 rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-600 hover:bg-slate-50"
            onClick={workspace.swapLanguages}
            title="Swap languages"
          >
            ⇄
          </button>
          <LanguageSelect
            label="Target language"
            value={workspace.targetLanguage}
            options={targetLanguages}
            onChange={workspace.setTargetLanguage}
          />
        </div>

        {workspace.translationError && (
          <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {workspace.translationError}
          </p>
        )}

        <button
          className="mt-5 w-full rounded-xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          type="submit"
          disabled={workspace.backendState !== "connected" || workspace.manualTranslating}
        >
          {workspace.manualTranslating ? "Translating…" : "Translate"}
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
          {workspace.translation && (
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
              {workspace.translation.provider}
            </span>
          )}
        </div>

        <div className="mt-5 min-h-64 rounded-xl border border-slate-200 bg-slate-50 p-4">
          {workspace.translation ? (
            <p className="whitespace-pre-wrap text-sm leading-7 text-slate-900">
              {workspace.translation.translated_text}
            </p>
          ) : (
            <p className="text-sm leading-6 text-slate-400">
              {workspace.autoTranslating
                ? "The current browser selection is being translated…"
                : "The translated text will appear here after the backend completes the request."}
            </p>
          )}
        </div>

        <dl className="mt-4 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            Detected source:{" "}
            <strong className="font-medium text-slate-700">
              {workspace.translation?.source_language ?? "—"}
            </strong>
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            Target:{" "}
            <strong className="font-medium text-slate-700">
              {workspace.translation?.target_language ?? workspace.targetLanguage}
            </strong>
          </div>
        </dl>

        {(workspace.browserSelection?.context_before ||
          workspace.browserSelection?.context_after) && (
          <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Nearby context
            </p>
            <p className="mt-2 line-clamp-4 text-xs leading-5 text-slate-500">
              {[
                workspace.browserSelection.context_before,
                workspace.browserSelection.text,
                workspace.browserSelection.context_after,
              ]
                .filter(Boolean)
                .join(" ")}
            </p>
          </div>
        )}
      </section>
    </section>
  )
}
