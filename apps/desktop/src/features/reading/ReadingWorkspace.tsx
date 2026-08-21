import type { TranslationWorkspaceController } from "../translation/useTranslationWorkspace"
import BrowserReadingContextPanel from "./BrowserReadingContextPanel"

export default function ReadingWorkspace({
  workspace,
}: {
  workspace: TranslationWorkspaceController
}) {
  const selection = workspace.readingSelection
  const browserPage = workspace.browserPage
  const isBrowserSelection = selection?.source_kind === "browser"
  const title =
    selection?.resource_title ||
    (isBrowserSelection ? browserPage?.title : "") ||
    "—"
  const section =
    selection?.section_heading ||
    (isBrowserSelection ? browserPage?.heading : "") ||
    "—"
  const locator =
    selection?.resource_url ||
    selection?.local_locator ||
    (isBrowserSelection ? browserPage?.url : "") ||
    "—"

  return (
    <div className="space-y-5">
      <BrowserReadingContextPanel
        browserStatus={workspace.browserStatus}
        readingSelection={selection}
        browserPage={browserPage}
        followBrowserSelection={workspace.followBrowserSelection}
        autoTranslateSelection={workspace.autoTranslateSelection}
        autoTranslating={workspace.autoTranslating}
        onFollowBrowserSelectionChange={workspace.setFollowBrowserSelection}
        onAutoTranslateSelectionChange={workspace.setAutoTranslateSelection}
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                Current selection
              </p>
              <h2 className="mt-2 text-lg font-semibold text-slate-900">
                {selection ? `${selection.text.length} characters captured` : "No selection yet"}
              </h2>
            </div>
            {selection && (
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                {selection.source_kind || "reading"} · {selection.provider}
              </span>
            )}
          </div>

          <div className="mt-5 min-h-48 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
              {selection?.text || "Select text in a browser, PDF, Word document, or another native app to inspect its bounded reading context here."}
            </p>
          </div>

          {selection && (
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              <ContextBlock label="Before" value={selection.context_before} />
              <ContextBlock label="After" value={selection.context_after} />
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
            Document metadata
          </p>
          <dl className="mt-4 space-y-4 text-sm">
            <MetadataRow label="Title" value={title} />
            <MetadataRow label="Section" value={section} />
            <MetadataRow label="Source" value={selection?.source_kind || "—"} />
            <MetadataRow label="Application" value={selection?.application || "—"} />
            <MetadataRow
              label="Page"
              value={selection?.page_number ? String(selection.page_number) : "—"}
            />
            <MetadataRow label="Locator" value={locator} mono />
            <MetadataRow
              label="Browser bridge"
              value={workspace.browserStatus?.has_extension_activity ? "Active" : "Waiting"}
            />
          </dl>
        </section>
      </div>
    </div>
  )
}

function ContextBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
      <p className="mt-2 line-clamp-6 text-xs leading-5 text-slate-600">{value || "No nearby context captured."}</p>
    </div>
  )
}

function MetadataRow({
  label,
  value,
  mono = false,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div>
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className={`mt-1 break-words text-slate-700 ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  )
}
