import { useEffect, useRef } from "react"
import { useQuery } from "@tanstack/react-query"
import { useLocation, useNavigate } from "react-router-dom"

import { getCompanionHandoff } from "../../api/companion"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"

export default function CompanionHandoffNavigator() {
  const navigate = useNavigate()
  const location = useLocation()
  const lastNavigatedHandoff = useRef("")

  const handoffQuery = useQuery({
    queryKey: queryKeys.companion.handoff,
    queryFn: getCompanionHandoff,
    refetchInterval: queryPolling.companionHandoff,
    staleTime: 0,
  })

  const handoffId = handoffQuery.data?.handoff?.handoff_id ?? ""

  useEffect(() => {
    if (!handoffId || handoffId === lastNavigatedHandoff.current) return
    lastNavigatedHandoff.current = handoffId
    if (location.pathname !== "/chat" || location.search) {
      navigate("/chat")
    }
  }, [handoffId, location.pathname, location.search, navigate])

  return null
}
