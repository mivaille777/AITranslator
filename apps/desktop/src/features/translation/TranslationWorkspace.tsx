import type { FormEvent } from "react"

import { LanguageSelect } from "../../shared/components/LanguageSelect"
import { sourceLanguages, targetLanguages } from "./languages"
import TranslationProviderSelector from "./TranslationProviderSelector"
import type { TranslationWorkspaceController } from "./useTranslationWorkspace"

export default function TranslationWorkspace({
  workspace,
}: {
  workspace: TranslationWorkspaceController
}) {
  const selection = workspace.readingSelection
  const providerDisabled =
    workspace.backendState !== "connected" ||
    workspace.providerSwitching ||
    workspace.manualTranslating ||
    workspace.autoTranslating

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    workspace.translateManual()
  }

  return (
    <section className="ait-surface overflow-hidden">
      <div className="grid xl:grid-cols-2">
        <form
          className="p-6 lg:p-7 xl:border-r xl:border-slate-200/70"
          onSubmit={handleSubmit}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Source</p>
              <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-950">Text to translate</h2>
              <p className="mt-1 text-sm text-slate-500">
                Enter text manually or use the latest unified reading selection.
              </p>
            </div>
            <button
              type="button"
              className="ait-control-motion rounded-[13px] border border-slate-200/80 bg-white px-3 py-2 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50"
              onClick={workspace.clear}
            >
              Clear
            </button>
          </div>

          <textarea
            className="mt-5 min-h-64 w-full resize-y rounded-[18px] border border-slate-200/80 bg-slate-50/80 p-4 text-sm leading-6 text-slate-900 outline-none transition focus:border-slate-400 focus:bg-white focus:shadow-sm"
            placeholder="Enter text, or select text in a browser, PDF, Word document, or another native app…"
            value={workspace.sourceText}
            onChange={(event) => workspace.updateSourceText(event.target.value)}
          />

          {selection && (
            <div className="mt-3 flex items-center justify-between gap-3 text-xs text-slate-500">
              <span className="truncate">
                Latest reading selection · {selection.text.length} chars · {selection.source_kind || selection.provider}
              </span>
              {!workspace.followBrowserSelection && (
                <button
                  type="button"
                  className="ait-control-motion shrink-0 rounded-lg px-2 py-1 font-medium text-slate-800 hover:bg-slate-100"
                  onClick={workspace.useLatestSelection}
                >
                  Use selection
                </button>
              )}
            </div>
          )}

          <div className="mt-4">
            <TranslationProviderSelector
              value={workspace.translationProvider}
              switching={workspace.providerSwitching}
              disabled={providerDisabled}
              description="Quick switch for manual and reading translations. The choice is also saved as your default."
              onChange={workspace.setTranslationProvider}
            />
          </div>

          <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-end gap-2">
            <LanguageSelect
              label="Source language"
              value={workspace.sourceLanguage}
              options={sourceLanguages}
              onChange={workspace.setSourceLanguage}
            />
            <button
              type="button"
              className="ait-control-motion mb-0.5 rounded-[13px] border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-600 shadow-sm hover:bg-slate-50"
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
            <p className="mt-4 rounded-[14px] border border-rose-100 bg-rose-50 px-3.5 py-2.5 text-sm text-rose-700">
              {workspace.translationError}
            </p>
          )}

          <button
            className="ait-control-motion mt-5 w-full rounded-[15px] bg-slate-950 px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            type="submit"
            disabled={
              workspace.backendState !== "connected" ||
              workspace.manualTranslating ||
              workspace.providerSwitching
            }
          >
            {workspace.manualTranslating ? "Translating…" : "Translate"}
          </button>
        </form>

        <section className="bg-slate-50/50 p-6 lg:p-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Translation</p>
              <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-950">Result</h2>
              <p className="mt-1 text-sm text-slate-500">
                The translated text stays attached to the active reading context.
              </p>
            </div>
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
              {workspace.translation?.provider ?? workspace.providerName}
            </span>
          </div>

          <div className="mt-5 min-h-64 rounded-[18px] border border-slate-200/70 bg-white/90 p-4 shadow-sm">
            {workspace.translation ? (
              <p className="whitespace-pre-wrap text-sm leading-7 text-slate-900">
                {workspace.translation.translated_text}
              </p>
            ) : (
              <p className="text-sm leading-6 text-slate-400">
                {workspace.autoTranslating
                  ? "The current reading selection is being translated…"
                  : "The translated text will appear here after the backend completes the request."}
              </p>
            )}
          </div>

          <dl className="mt-4 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
            <div className="rounded-[13px] border border-slate-200/60 bg-white/75 px-3 py-2.5">
              Detected source:{" "}
              <strong className="font-medium text-slate-700">
                {workspace.translation?.source_language ?? "—"}
              </strong>
            </div>
            <div className="rounded-[13px] border border-slate-200/60 bg-white/75 px-3 py-2.5">
              Target:{" "}
              <strong className="font-medium text-slate-700">
                {workspace.translation?.target_language ?? workspace.targetLanguage}
              </strong>
            </div>
          </dl>

          {(selection?.context_before || selection?.context_after) && (
            <div className="mt-4 rounded-[16px] border border-slate-200/60 bg-white/75 p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                Nearby context
              </p>
              <p className="mt-2 line-clamp-4 text-xs leading-5 text-slate-500">
                {[
                  selection.context_before,
                  selection.text,
                  selection.context_after,
                ].filter(Boolean).join(" ")}
              </p>
            </div>
          )}
        </section>
      </div>
    </section>
  )
}
