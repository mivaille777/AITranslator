import { useEffect, useRef } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useLocation, useNavigate } from "react-router-dom"

import {
  dismissCompanionHandoff,
  getCompanionHandoff,
} from "../../api/companion"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"
import { companionHandoffPath } from "./companion-handoff-navigation"

export default function CompanionHandoffNavigator() {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const initialized = useRef(false)
  const lastNavigatedHandoff = useRef("")

  const handoffQuery = useQuery({
    queryKey: queryKeys.companion.handoff,
    queryFn: getCompanionHandoff,
    refetchInterval: queryPolling.companionHandoff,
    staleTime: 0,
  })

  const handoff = handoffQuery.data?.handoff ?? null
  const handoffId = handoff?.handoff_id ?? ""
  const conversationId = (handoff?.conversation_id ?? "").trim()
  const destination = companionHandoffPath(handoff)

  useEffect(() => {
    if (!handoffQuery.isSuccess) return

    if (!initialized.current) {
      initialized.current = true
      lastNavigatedHandoff.current = handoffId
      return
    }

    if (!handoffId || handoffId === lastNavigatedHandoff.current) return
    lastNavigatedHandoff.current = handoffId

    const currentPath = `${location.pathname}${location.search}`
    if (destination && currentPath !== destination) {
      navigate(destination)
    }

    if (conversationId) {
      // Conversation-aware handoffs are transient cross-window navigation
      // signals. The persisted conversation is the source of truth after route
      // selection, so clear the signal instead of leaving stale reading state.
      void dismissCompanionHandoff(handoffId).finally(() => {
        void queryClient.invalidateQueries({ queryKey: queryKeys.companion.handoff })
      })
    }
  }, [
    conversationId,
    destination,
    handoffId,
    handoffQuery.isSuccess,
    location.pathname,
    location.search,
    navigate,
    queryClient,
  ])

  return null
}
