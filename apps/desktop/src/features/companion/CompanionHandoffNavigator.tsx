import { useEffect, useRef } from "react"
import { useQuery } from "@tanstack/react-query"
import { useLocation, useNavigate } from "react-router-dom"

import { getCompanionHandoff } from "../../api/companion"

export default function CompanionHandoffNavigator() {
  const navigate = useNavigate()
  const location = useLocation()
  const lastNavigatedHandoff = useRef("")

  const handoffQuery = useQuery({
    queryKey: ["companion-handoff"],
    queryFn: getCompanionHandoff,
    refetchInterval: 650,
    staleTime: 0,
    retry: 1,
  })

  const handoffId = handoffQuery.data?.handoff?.handoff_id ?? ""

  useEffect(() => {
    if (!handoffId || handoffId === lastNavigatedHandoff.current) return
    lastNavigatedHandoff.current = handoffId
    if (location.pathname !== "/chat") navigate("/chat")
  }, [handoffId, location.pathname, navigate])

  return null
}
