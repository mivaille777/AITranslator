import type {
  BrowserBridgeStatusResponse,
  BrowserPage,
  BrowserSelection,
} from "../../api/types"
import { Toggle } from "../../shared/components/Toggle"

export default function BrowserReadingContextPanel({
  browserStatus,
  browserSelection,
  browserPage,
  followBrowserSelection,
  autoTranslateSelection,
  autoTranslating,
  onFollowBrowserSelectionChange,
  onAutoTranslateSelectionChange,
}: {
  browserStatus: BrowserBridgeStatusResponse | undefined
  browserSelection: BrowserSelection | null
  browserPage: BrowserPage | null
  followBrowserSelection: boolean
  autoTranslateSelection: boolean
  autoTranslating: boolean
  onFollowBrowserSelectionChange: (checked: boolean) => void
  onAutoTranslateSelectionChange: (checked: boolean) => void
}) {
  const title = browserPage?.title || browserSelection?.title || "Waiting for the browser extension…"
  const url = browserPage?.url || browserSelection?.url || ""
  const heading = browserSelection?.heading || browserPage?.heading || ""

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">Browser Reading Context</h2>
            <span
              className={`h-2 w-2 rounded-full ${
                browserStatus?.has_extension_activity
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
            checked={followBrowserSelection}
            onChange={onFollowBrowserSelectionChange}
          />
          <Toggle
            label={autoTranslating ? "Auto translating…" : "Auto translate + overlay"}
            checked={autoTranslateSelection}
            onChange={onAutoTranslateSelectionChange}
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
