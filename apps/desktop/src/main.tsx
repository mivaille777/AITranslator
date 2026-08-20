import { StrictMode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createRoot } from 'react-dom/client'

import App from './App'
import OverlayQuickActionDock from './components/OverlayQuickActionDock'
import OverlayView from './components/OverlayView'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 1_000,
    },
  },
})

const view = new URLSearchParams(window.location.search).get('view')
const rootView = view === 'overlay'
  ? (
      <>
        <OverlayView />
        <OverlayQuickActionDock />
      </>
    )
  : <App />

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {rootView}
    </QueryClientProvider>
  </StrictMode>,
)
