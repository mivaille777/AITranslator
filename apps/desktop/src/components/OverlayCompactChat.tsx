import { lazy, Suspense } from "react"

import type {
  OverlayStateResponse,
  QuickActionResponse,
} from "../api/types"

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
  return (
    <div className="ait-overlay-chat-panel min-h-0">
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
