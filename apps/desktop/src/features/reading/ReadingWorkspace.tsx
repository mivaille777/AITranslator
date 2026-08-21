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
    <div className="space-y-4">
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

      <section className="ait-surface overflow-hidden">
        <div className="grid xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
          <div className="p-6 lg:p-7">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Current selection
                </p>
                <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-950">
                  {selection ? `${selection.text.length} characters captured` : "No selection yet"}
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Frozen evidence that can be translated, discussed, or saved as research.
                </p>
              </div>
              {selection && (
                <span className="rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                  {selection.source_kind || "reading"} · {selection.provider}
                </span>
              )}
            </div>

            <div className="mt-5 min-h-52 rounded-[20px] border border-slate-200/70 bg-slate-50/80 p-5">
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
          </div>

          <aside className="border-t border-slate-200/70 bg-slate-50/60 p-6 lg:p-7 xl:border-l xl:border-t-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Document metadata
            </p>
            <dl className="mt-5 space-y-4 text-sm">
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
          </aside>
        </div>
      </section>
    </div>
  )
}

function ContextBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[16px] border border-slate-200/60 bg-white/75 p-4">
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
    <div className="rounded-[14px] border border-slate-200/60 bg-white/70 px-3.5 py-3">
      <dt className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-400">{label}</dt>
      <dd className={`mt-1.5 break-words text-slate-700 ${mono ? "font-mono text-xs" : "text-sm"}`}>{value}</dd>
    </div>
  )
}
