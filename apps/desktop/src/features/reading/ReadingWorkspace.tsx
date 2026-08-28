import { BookOpenText } from "lucide-react"

import type { TranslationWorkspaceController } from "../translation/useTranslationWorkspace"
import AcademicDocumentWorkspacePanel from "./AcademicDocumentWorkspacePanel"
import BrowserReadingContextPanel from "./BrowserReadingContextPanel"
import { useAcademicDocumentWorkspace } from "./useAcademicDocumentWorkspace"

export default function ReadingWorkspace({
  workspace,
}: {
  workspace: TranslationWorkspaceController
}) {
  const academicWorkspace = useAcademicDocumentWorkspace(workspace)
  const selection = workspace.readingSelection
  const browserPage = workspace.browserPage
  const isBrowserSelection = selection?.source_kind === "browser"
  const title = selection?.resource_title || (isBrowserSelection ? browserPage?.title : "") || "—"
  const section = selection?.section_heading || (isBrowserSelection ? browserPage?.heading : "") || "—"
  const locator = selection?.resource_url || selection?.local_locator || (isBrowserSelection ? browserPage?.url : "") || "—"
  const hasNearbyContext = Boolean(selection?.context_before || selection?.context_after)

  return (
    <div className="space-y-4">
      <AcademicDocumentWorkspacePanel controller={academicWorkspace} />

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
        <div className="grid xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.6fr)]">
          <div className="p-6 lg:p-7">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                  External reading selection
                </p>
                <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-950">
                  {selection ? `${selection.text.length} characters captured` : "No external selection yet"}
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Browser and desktop selections remain available alongside the academic document workspace.
                </p>
              </div>
              {selection && (
                <span className="rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                  {selection.source_kind || "reading"} · {selection.provider}
                </span>
              )}
            </div>

            {selection ? (
              <div className="mt-5 rounded-[20px] border border-slate-200/70 bg-slate-50/75 p-5">
                <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">{selection.text}</p>
              </div>
            ) : (
              <div className="mt-5 flex min-h-40 items-center gap-4 rounded-[20px] border border-slate-200/60 bg-slate-50/55 p-5">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[15px] border border-slate-200/70 bg-white text-slate-400 shadow-sm">
                  <BookOpenText size={20} strokeWidth={1.6} />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">Select text in any supported external reading source.</p>
                  <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500">
                    Browser DOM, browser PDF accessibility, Word COM, and generic desktop UIA still resolve into the same reading contract.
                  </p>
                </div>
              </div>
            )}

            {selection && hasNearbyContext && (
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                <ContextBlock label="Before" value={selection.context_before} />
                <ContextBlock label="After" value={selection.context_after} />
              </div>
            )}

            {selection && !hasNearbyContext && (
              <p className="mt-4 text-xs text-slate-400">
                This provider did not expose bounded nearby text for the current selection.
              </p>
            )}
          </div>

          <aside className="border-t border-slate-200/70 bg-slate-50/55 p-6 lg:p-7 xl:border-l xl:border-t-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              External source metadata
            </p>

            {selection ? (
              <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
                <MetadataRow label="Title" value={title} span />
                <MetadataRow label="Section" value={section} span />
                <MetadataRow label="Source" value={selection.source_kind || "—"} />
                <MetadataRow label="Application" value={selection.application || "—"} />
                <MetadataRow label="Page" value={selection.page_number ? String(selection.page_number) : "—"} />
                <MetadataRow label="Provider" value={selection.provider || "—"} />
                <MetadataRow label="Locator" value={locator} mono span />
              </dl>
            ) : (
              <div className="mt-5 rounded-[18px] border border-slate-200/60 bg-white/65 p-4">
                <p className="text-sm font-medium text-slate-700">Metadata follows the external selection.</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  Academic document metadata and outline are managed independently above.
                </p>
              </div>
            )}
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
  span = false,
}: {
  label: string
  value: string
  mono?: boolean
  span?: boolean
}) {
  return (
    <div className={`rounded-[14px] border border-slate-200/60 bg-white/72 px-3.5 py-3 ${span ? "col-span-2" : ""}`}>
      <dt className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-400">{label}</dt>
      <dd className={`mt-1.5 break-words text-slate-700 ${mono ? "font-mono text-[11px]" : "text-sm"}`}>{value}</dd>
    </div>
  )
}
