import type { ReactNode } from "react"
import { Minus, Square, X } from "lucide-react"
import { getCurrentWindow } from "@tauri-apps/api/window"

import "./WindowFrame.css"

export default function WindowFrame({ children }: { children: ReactNode }) {
  const window = getCurrentWindow()

  return (
    <div className="window-frame">
      <header className="window-titlebar" data-tauri-drag-region>
        <div className="window-brand" data-tauri-drag-region>
          <span className="window-logo">A</span>
          <div>
            <span>AITranslator</span>
            <small>Desktop Agent</small>
          </div>
        </div>

        <div className="window-drag-space" data-tauri-drag-region />

        <div className="window-status" data-tauri-drag-region>
          <span /> Ready
        </div>

        <div className="window-controls">
          <button title="Minimize" aria-label="Minimize" onClick={() => window.minimize()}>
            <Minus size={12} strokeWidth={2.2} />
          </button>
          <button title="Maximize" aria-label="Maximize" onClick={() => window.toggleMaximize()}>
            <Square size={11} strokeWidth={2.2} />
          </button>
          <button title="Close" className="close" aria-label="Close" onClick={() => window.close()}>
            <X size={13} strokeWidth={2.2} />
          </button>
        </div>
      </header>
      <div className="window-content">{children}</div>
    </div>
  )
}
