import { StrictMode } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"
import { HashRouter } from "react-router-dom"

import App from "./App"
import AppErrorBoundary from "./shared/errors/AppErrorBoundary"
import { createAppQueryClient } from "./shared/query/query-client"
import "./index.css"

document.documentElement.dataset.aitView = "main"

const queryClient = createAppQueryClient()

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppErrorBoundary>
        <HashRouter>
          <App />
        </HashRouter>
      </AppErrorBoundary>
    </QueryClientProvider>
  </StrictMode>,
)
