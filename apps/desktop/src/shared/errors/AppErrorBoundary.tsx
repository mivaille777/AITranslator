import { Component, type ErrorInfo, type ReactNode } from "react"

import { Button } from "../ui/Button"

interface AppErrorBoundaryState {
  error: Error | null
}

export default class AppErrorBoundary extends Component<
  { children: ReactNode },
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("AITranslator frontend crashed", error, info)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 p-6 text-slate-950">
        <section className="w-full max-w-lg rounded-2xl border border-rose-200 bg-white p-6 shadow-xl">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-rose-500">
            Frontend recovery
          </p>
          <h1 className="mt-2 text-xl font-semibold">The workspace could not render.</h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            The FastAPI backend and native overlay are separate processes. Reloading this WebView is safe and does not reset server-side Research Notes.
          </p>
          <pre className="mt-4 max-h-36 overflow-auto rounded-xl bg-slate-950 p-3 text-xs leading-5 text-slate-300">
            {this.state.error.message}
          </pre>
          <Button
            variant="primary"
            className="mt-4"
            onClick={() => window.location.reload()}
          >
            Reload workspace
          </Button>
        </section>
      </main>
    )
  }
}
