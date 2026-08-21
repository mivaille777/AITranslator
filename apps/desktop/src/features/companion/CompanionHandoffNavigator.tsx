import { useEffect, useRef } from "react"
import { useQuery } from "@tanstack/react-query"
import { useLocation, useNavigate } from "react-router-dom"

import { getCompanionHandoff } from "../../api/companion"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"

export default function CompanionHandoffNavigator() {
  const navigate = useNavigate()
  const location = useLocation()
  const initialized = useRef(false)
  const lastNavigatedHandoff = useRef("")

  const handoffQuery = useQuery({
    queryKey: queryKeys.companion.handoff,
    queryFn: getCompanionHandoff,
    refetchInterval: queryPolling.companionHandoff,
    staleTime: 0,
  })

  const handoffId = handoffQuery.data?.handoff?.handoff_id ?? ""

  useEffect(() => {
    if (!handoffQuery.isSuccess) return

    if (!initialized.current) {
      initialized.current = true
      lastNavigatedHandoff.current = handoffId
      return
    }

    if (!handoffId || handoffId === lastNavigatedHandoff.current) return
    lastNavigatedHandoff.current = handoffId
    if (location.pathname !== "/chat" || location.search) {
      navigate("/chat")
    }
  }, [handoffId, handoffQuery.isSuccess, location.pathname, location.search, navigate])

  return null
}
