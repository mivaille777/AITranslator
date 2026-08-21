import { StrictMode } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"
import { HashRouter } from "react-router-dom"

import App from "./App"
import OverlayView from "./components/OverlayView"
import AppErrorBoundary from "./shared/errors/AppErrorBoundary"
import { createAppQueryClient } from "./shared/query/query-client"
import "./index.css"
import "./overlay.css"

const queryClient = createAppQueryClient()

const view = new URLSearchParams(window.location.search).get("view")
if (view === "overlay") {
  document.documentElement.dataset.aitView = "overlay"
}

const rootView = view === "overlay"
  ? <OverlayView />
  : (
      <HashRouter>
        <App />
      </HashRouter>
    )

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppErrorBoundary>{rootView}</AppErrorBoundary>
    </QueryClientProvider>
  </StrictMode>,
)
