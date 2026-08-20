import { Toggle } from "../../shared/components/Toggle"
import type { TranslationWorkspaceController } from "../translation/useTranslationWorkspace"

export default function BrowserReadingContextPanel({
  workspace,
}: {
  workspace: TranslationWorkspaceController
}) {
  const selection = workspace.browserSelection
  const page = workspace.browserPage
  const title = page?.title || selection?.title || "Waiting for the browser extension…"
  const url = page?.url || selection?.url || ""
  const heading = selection?.heading || page?.heading || ""

  return (
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">Browser Reading Context</h2>
            <span
              className={`h-2 w-2 rounded-full ${
                workspace.browserStatus?.has_extension_activity
                  ? "bg-emerald-500"
                  : "bg-slate-300"
              }`}
            />
          </div>
          <p className="mt-1 truncate text-sm text-slate-500">{title}</p>
          {url && <p className="mt-1 truncate text-xs text-slate-400">{url}</p>}
        </div>

        <div className="flex flex-wrap gap-2">
          <Toggle
            label="Follow selection"
            checked={workspace.followBrowserSelection}
            onChange={workspace.setFollowBrowserSelection}
          />
          <Toggle
            label={
              workspace.autoTranslating
                ? "Auto translating…"
                : "Auto translate + overlay"
            }
            checked={workspace.autoTranslateSelection}
            onChange={workspace.setAutoTranslateSelection}
          />
        </div>
      </div>

      {heading && (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
          Section: <strong className="font-medium text-slate-700">{heading}</strong>
        </p>
      )}
    </section>
  )
}
