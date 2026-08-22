import type { OverlayStateResponse } from "../api/types"
import { resolveOverlaySourceIdentity } from "./overlay-source-identity"

export default function OverlaySourceContext({ state }: { state: OverlayStateResponse }) {
  const identity = resolveOverlaySourceIdentity({
    application: state.application,
    sourceKind: state.source_kind,
    resourceUrl: state.resource_url,
    resourceTitle: state.resource_title,
    sectionHeading: state.section_heading,
  })

  return (
    <div
      className="ait-overlay-source-context border-b border-white/[0.065] px-4 py-2.5"
      data-ait-selection-scope="internal"
      title={identity.tooltip || undefined}
    >
      <div className="flex min-w-0 items-center gap-1.5">
        <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-400" aria-hidden="true" />
        <span className="truncate text-[11px] font-semibold text-slate-200">
          {identity.applicationLabel}
        </span>
        {identity.detail && (
          <>
            <span className="shrink-0 text-[9px] text-slate-600" aria-hidden="true">·</span>
            <span className="truncate text-[9px] text-slate-500">
              {identity.detail}
            </span>
          </>
        )}
      </div>
      <p className="mt-1 truncate pl-3.5 text-[10px] text-slate-500">
        {identity.title}
      </p>
    </div>
  )
}
