import { StrictMode } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"

import OverlayView from "./components/OverlayView"
import { desktop } from "./desktop"
import AppErrorBoundary from "./shared/errors/AppErrorBoundary"
import { createAppQueryClient } from "./shared/query/query-client"
import { queryKeys } from "./shared/query/query-keys"
import "./index.css"
import "./overlay.css"
import "./overlay-fix.css"
import "./overlay-mode-navigation.css"

document.documentElement.dataset.aitView = "overlay"

const queryClient = createAppQueryClient()

void desktop.overlay.onStateChanged(() => {
  void queryClient.refetchQueries({ queryKey: queryKeys.overlay.state, type: "active" })
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppErrorBoundary>
        <OverlayView />
      </AppErrorBoundary>
    </QueryClientProvider>
  </StrictMode>,
)
