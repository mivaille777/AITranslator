import { useCallback, useEffect, useRef } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useLocation, useNavigate } from "react-router-dom"

import {
  dismissCompanionHandoff,
  getCompanionHandoff,
} from "../../api/companion"
import { desktop } from "../../desktop"
import { queryKeys, queryPolling } from "../../shared/query/query-keys"
import {
  companionConversationPath,
  companionHandoffPath,
} from "./companion-handoff-navigation"

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

  const consumeConversationNavigation = useCallback((
    nextConversationId: string,
    nextHandoffId: string,
  ) => {
    const normalizedConversationId = nextConversationId.trim()
    if (!normalizedConversationId) return

    if (nextHandoffId) {
      lastNavigatedHandoff.current = nextHandoffId
    }
    navigate(companionConversationPath(normalizedConversationId))

    if (nextHandoffId) {
      void dismissCompanionHandoff(nextHandoffId).finally(() => {
        void queryClient.invalidateQueries({ queryKey: queryKeys.companion.handoff })
      })
    }
  }, [navigate, queryClient])

  useEffect(() => {
    let disposed = false
    let unlisten = () => undefined

    void desktop.overlay.onCompanionNavigation((signal) => {
      if (disposed) return
      consumeConversationNavigation(signal.conversationId, signal.handoffId)
    }).then((stopListening) => {
      if (disposed) {
        stopListening()
        return
      }
      unlisten = stopListening
    })

    return () => {
      disposed = true
      unlisten()
    }
  }, [consumeConversationNavigation])

  useEffect(() => {
    if (!handoffQuery.isSuccess) return

    if (!initialized.current) {
      initialized.current = true
      if (!conversationId) {
        // Preserve the old startup behavior for context-only handoffs: they may
        // be stale state from before the workspace mounted. Conversation-aware
        // handoffs are transient navigation signals and must never be dropped.
        lastNavigatedHandoff.current = handoffId
        return
      }
    }

    if (!handoffId || handoffId === lastNavigatedHandoff.current) return

    if (conversationId) {
      consumeConversationNavigation(conversationId, handoffId)
      return
    }

    lastNavigatedHandoff.current = handoffId
    const currentPath = `${location.pathname}${location.search}`
    if (destination && currentPath !== destination) {
      navigate(destination)
    }
  }, [
    consumeConversationNavigation,
    conversationId,
    destination,
    handoffId,
    handoffQuery.isSuccess,
    location.pathname,
    location.search,
    navigate,
  ])

  return null
}
