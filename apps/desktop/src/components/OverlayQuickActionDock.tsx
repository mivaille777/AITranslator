import { useQuery } from "@tanstack/react-query"

import { getOverlayState } from "../api/overlay"
import OverlayQuickActions from "./OverlayQuickActions"

export default function OverlayQuickActionDock() {
  const overlayQuery = useQuery({
    queryKey: ["overlay-state"],
    queryFn: getOverlayState,
    refetchInterval: 250,
    retry: 1,
    staleTime: 0,
  })

  const state = overlayQuery.data
  if (!state?.visible || state.phase !== "ready") return null

  return (
    <div className="pointer-events-none fixed inset-x-2 bottom-[52px] z-40 max-h-[58vh] overflow-y-auto rounded-2xl bg-slate-900/95 shadow-2xl backdrop-blur">
      <div className="pointer-events-auto">
        <OverlayQuickActions state={state} />
      </div>
    </div>
  )
}
