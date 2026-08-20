import { useEffect, useState } from "react"

import { getHealth } from "./api/health"
import { desktop } from "./desktop"

type BackendState = "checking" | "connected" | "offline"

function App() {
  const [backendState, setBackendState] = useState<BackendState>("checking")
  const [serviceName, setServiceName] = useState("aitrans-backend")

  useEffect(() => {
    let active = true

    getHealth()
      .then((health) => {
        if (!active) return
        setServiceName(health.service)
        setBackendState("connected")
      })
      .catch(() => {
        if (!active) return
        setBackendState("offline")
      })

    return () => {
      active = false
    }
  }, [])

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 text-slate-950">
      <section className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
          Stage 1 foundation
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">
          AITranslator WebReBuild
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          React, the Python API boundary, and the replaceable desktop adapter are now wired together.
        </p>

        <dl className="mt-8 grid gap-3 text-sm">
          <div className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-3">
            <dt className="text-slate-500">Desktop runtime</dt>
            <dd className="font-medium capitalize text-slate-900">{desktop.runtime}</dd>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-3">
            <dt className="text-slate-500">Backend</dt>
            <dd className="font-medium text-slate-900">
              {backendState === "checking" && "Checking…"}
              {backendState === "connected" && `${serviceName} · Connected`}
              {backendState === "offline" && "Offline · start Python API on :8765"}
            </dd>
          </div>
        </dl>
      </section>
    </main>
  )
}

export default App
