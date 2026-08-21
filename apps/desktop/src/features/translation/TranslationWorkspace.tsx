import type { FormEvent } from "react"

import AITButton from "../../shared/components/AITButton"
import AITInput from "../../shared/components/AITInput"
import AITPanel from "../../shared/components/AITPanel"
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
    <AITPanel className="overflow-hidden">
      <div className="grid xl:grid-cols-2">
        <form className="p-6 lg:p-7 xl:border-r xl:border-slate-200/70" onSubmit={handleSubmit}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Source</p>
              <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-950">Text to translate</h2>
              <p className="mt-1 text-sm text-slate-500">Enter text manually or use the latest unified reading selection.</p>
            </div>
            <AITButton variant="secondary" type="button" onClick={workspace.clear}>Clear</AITButton>
          </div>

          <AITInput
            className="mt-5 min-h-64"
            placeholder="Enter text, or select text in a browser, PDF, Word document, or another native app…"
            value={workspace.sourceText}
            onChange={(event) => workspace.updateSourceText(event.target.value)}
          />

          {selection && (
            <div className="mt-3 flex items-center justify-between gap-3 text-xs text-slate-500">
              <span className="truncate">Latest reading selection · {selection.text.length} chars · {selection.source_kind || selection.provider}</span>
              {!workspace.followBrowserSelection && (
                <button type="button" className="ait-control-motion shrink-0 rounded-lg px-2 py-1 font-medium text-slate-800 hover:bg-slate-100" onClick={workspace.useLatestSelection}>
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
            <LanguageSelect label="Source language" value={workspace.sourceLanguage} options={sourceLanguages} onChange={workspace.setSourceLanguage} />
            <button type="button" className="ait-control-motion mb-0.5 rounded-[13px] border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-600 shadow-sm hover:bg-slate-50" onClick={workspace.swapLanguages} title="Swap languages">⇄</button>
            <LanguageSelect label="Target language" value={workspace.targetLanguage} options={targetLanguages} onChange={workspace.setTargetLanguage} />
          </div>

          {workspace.translationError && <p className="mt-4 rounded-[14px] border border-rose-100 bg-rose-50 px-3.5 py-2.5 text-sm text-rose-700">{workspace.translationError}</p>}

          <AITButton
            className="mt-5 w-full"
            variant="primary"
            type="submit"
            disabled={workspace.backendState !== "connected" || workspace.manualTranslating || workspace.providerSwitching}
          >
            {workspace.manualTranslating ? "Translating…" : "Translate"}
          </AITButton>
        </form>

        <section className="bg-slate-50/50 p-6 lg:p-7">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Translation</p>
            <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-950">Result</h2>
          </div>
          <div className="mt-5 min-h-64 rounded-[16px] border border-slate-200/70 bg-white/90 p-4 shadow-sm">
            {workspace.translation ? <p className="whitespace-pre-wrap text-sm leading-7 text-slate-900">{workspace.translation.translated_text}</p> : <p className="text-sm text-slate-400">{workspace.autoTranslating ? "The current reading selection is being translated…" : "The translated text will appear here after the backend completes the request."}</p>}
          </div>
        </section>
      </div>
    </AITPanel>
  )
}
