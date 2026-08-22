import { lazy, Suspense } from "react"

import type {
  OverlayStateResponse,
  QuickActionResponse,
} from "../api/types"
import OverlaySourceContext from "./OverlaySourceContext"

const OverlayCompactChatContent = lazy(() => import("./OverlayCompactChatContent"))

export default function OverlayCompactChat({
  state,
  aiResult,
  onClose,
}: {
  state: OverlayStateResponse
  aiResult: QuickActionResponse | null
  onClose: () => void
}) {
  const notice = state.translation_notice?.trim() ?? ""

  return (
    <div className="ait-overlay-chat-panel min-h-0">
      <OverlaySourceContext state={state} />
      {notice && (
        <div
          data-ait-selection-scope="internal"
          className="border-b border-amber-300/15 bg-amber-300/[0.08] px-3 py-2 text-[10px] leading-4 text-amber-100/85"
        >
          {notice}
        </div>
      )}
      <Suspense
        fallback={(
          <div className="flex h-[240px] items-center justify-center gap-2 bg-black/10 text-[10px] text-slate-500">
            <span className="h-3 w-3 animate-spin rounded-full border border-white/20 border-t-white/70" />
            Loading AI Chat…
          </div>
        )}
      >
        <OverlayCompactChatContent
          state={state}
          aiResult={aiResult}
          onClose={onClose}
        />
      </Suspense>
    </div>
  )
}
