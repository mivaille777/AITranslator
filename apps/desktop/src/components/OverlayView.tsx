import { useEffect, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { dismissOverlay, getOverlayState } from "../api/overlay"
import { desktop } from "../desktop"

export default function OverlayView() {
  const [copied, setCopied] = useState(false)
  const overlayQuery = useQuery({
    queryKey: ["overlay-state"],
    queryFn: getOverlayState,
    refetchInterval: 250,
    retry: 1,
    staleTime: 0,
  })

  const dismissMutation = useMutation({
    mutationFn: dismissOverlay,
    onSuccess: () => {
      void desktop.window.hide()
    },
  })

  const state = overlayQuery.data

  useEffect(() => {
    if (!state) return
    if (state.visible) {
      void desktop.window.show()
    } else {
      void desktop.window.hide()
    }
  }, [state?.revision, state?.visible])

  async function handleCopy() {
    if (!state?.translated_text) return
    try {
      await navigator.clipboard.writeText(state.translated_text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 900)
    } catch {
      setCopied(false)
    }
  }

  if (!state?.visible) {
    return <div className="h-screen w-screen bg-transparent" />
  }

  return (
    <main className="h-screen w-screen overflow-hidden bg-slate-950 p-2 text-slate-100">
      <section className="flex h-full flex-col rounded-2xl border border-white/10 bg-slate-900 p-4 shadow-2xl">
        <header className="flex items-center justify-between gap-3 border-b border-white/10 pb-3">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              AITranslator
            </p>
            <p className="mt-1 truncate text-xs text-slate-500">
              {state.source_language} → {state.target_language}
              {state.provider ? ` · ${state.provider}` : ""}
            </p>
          </div>
          <button
            type="button"
            aria-label="Close overlay"
            className="rounded-lg px-2.5 py-1.5 text-sm text-slate-400 transition hover:bg-white/10 hover:text-white"
            onClick={() => dismissMutation.mutate()}
          >
            ×
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto py-4">
          {state.phase === "loading" && (
            <div className="flex h-full min-h-24 items-center justify-center gap-3 text-sm text-slate-300">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-slate-200" />
              Translating…
            </div>
          )}

          {state.phase === "ready" && (
            <div>
              <p className="whitespace-pre-wrap text-sm leading-6 text-slate-100">
                {state.translated_text}
              </p>
              {state.source_text && (
                <p className="mt-4 line-clamp-3 border-t border-white/10 pt-3 text-xs leading-5 text-slate-500">
                  {state.source_text}
                </p>
              )}
            </div>
          )}

          {state.phase === "error" && (
            <div className="rounded-xl border border-rose-400/20 bg-rose-400/10 p-3 text-sm leading-6 text-rose-200">
              {state.message || "Translation failed"}
            </div>
          )}
        </div>

        {state.phase === "ready" && (
          <footer className="flex justify-end border-t border-white/10 pt-3">
            <button
              type="button"
              className="rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-white/15"
              onClick={() => void handleCopy()}
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </footer>
        )}
      </section>
    </main>
  )
}
