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
      ? "Browser DOM bridge ready · Native readers also available"
      : "Waiting for Browser DOM / PDF UIA / Word / Desktop UIA"

  return (
    <section className="rounded-[24px] border border-slate-200/70 bg-white/90 p-5 shadow-[0_12px_38px_rgba(15,23,42,0.055)] backdrop-blur-xl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <span
              className={`h-2 w-2 rounded-full ${
                readingSelection || browserStatus?.has_extension_activity
                  ? "bg-emerald-500"
                  : "bg-slate-300"
              }`}
            />
            <h2 className="text-sm font-semibold tracking-tight text-slate-900">Unified Reading Context</h2>
            {readingSelection && (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                {readingSelection.source_kind || "reading"}
              </span>
            )}
          </div>
          <p className="mt-2 truncate text-sm text-slate-600">{title}</p>
          {locator && <p className="mt-1 truncate text-xs text-slate-400">{locator}</p>}
          <p className="mt-1.5 text-[10px] font-medium uppercase tracking-[0.13em] text-slate-400">
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
        <p className="mt-4 rounded-[14px] border border-slate-200/60 bg-slate-50/80 px-3.5 py-2.5 text-xs text-slate-500">
          Section: <strong className="font-medium text-slate-700">{heading}</strong>
        </p>
      )}
    </section>
  )
}
