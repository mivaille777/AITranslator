import { useQuery } from "@tanstack/react-query"

import { getOverlayState } from "../api/overlay"
import { queryKeys, queryPolling } from "../shared/query/query-keys"
import OverlayQuickActions from "./OverlayQuickActions"

export default function OverlayQuickActionDock() {
  const overlayQuery = useQuery({
    queryKey: queryKeys.overlay.state,
    queryFn: getOverlayState,
    refetchInterval: queryPolling.overlayState,
    staleTime: 0,
  })

  const state = overlayQuery.data
  if (!state?.visible || state.phase !== "ready") return null

  return (
    <div className="ait-overlay-actions-dock pointer-events-none fixed inset-x-2 bottom-[52px] z-40 max-h-[58vh] overflow-y-auto rounded-[18px]">
      <div className="pointer-events-auto">
        <OverlayQuickActions state={state} />
      </div>
    </div>
  )
}
