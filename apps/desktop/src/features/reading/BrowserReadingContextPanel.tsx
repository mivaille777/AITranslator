import type { ReadingSelection } from "../../api/reading"
import type {
  BrowserBridgeStatusResponse,
  BrowserPage,
} from "../../api/types"
import { Toggle } from "../../shared/components/Toggle"

export default function BrowserReadingContextPanel({
  browserStatus,
  browserPage,
  readingSelection,
  followBrowserSelection,
  autoTranslateSelection,
  autoTranslating,
  onFollowBrowserSelectionChange,
  onAutoTranslateSelectionChange,
}: {
  browserStatus: BrowserBridgeStatusResponse | undefined
  browserPage: BrowserPage | null
  readingSelection: ReadingSelection | null
  followBrowserSelection: boolean
  autoTranslateSelection: boolean
  autoTranslating: boolean
  onFollowBrowserSelectionChange: (checked: boolean) => void
  onAutoTranslateSelectionChange: (checked: boolean) => void
}) {
  const isBrowserSelection = readingSelection?.source_kind === "browser"
  const title =
    readingSelection?.resource_title ||
    (isBrowserSelection ? browserPage?.title : "") ||
    "Waiting for a reading selection…"
  const locator =
    readingSelection?.resource_url ||
    readingSelection?.local_locator ||
    (isBrowserSelection ? browserPage?.url : "") ||
    ""
  const heading =
    readingSelection?.section_heading ||
    (isBrowserSelection ? browserPage?.heading : "") ||
    ""
  const captureLabel = readingSelection
    ? `${readingSelection.source_kind || "reading"} · ${readingSelection.provider}`
    : browserStatus?.has_extension_activity
      ? "Browser bridge ready"
      : "Waiting for Browser DOM / UIA / Word"

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">Unified Reading Context</h2>
            <span
              className={`h-2 w-2 rounded-full ${
                readingSelection || browserStatus?.has_extension_activity
                  ? "bg-emerald-500"
                  : "bg-slate-300"
              }`}
            />
          </div>
          <p className="mt-1 truncate text-sm text-slate-500">{title}</p>
          {locator && <p className="mt-1 truncate text-xs text-slate-400">{locator}</p>}
          <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.12em] text-slate-400">
            {captureLabel}
          </p>
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
