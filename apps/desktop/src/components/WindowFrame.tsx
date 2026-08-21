import type { ReactNode } from "react"
import { getCurrentWindow } from "@tauri-apps/api/window"

import "./WindowFrame.css"

export default function WindowFrame({ children }: { children: ReactNode }) {
  const window = getCurrentWindow()

  return (
    <div className="window-frame">
      <header className="window-titlebar" data-tauri-drag-region>
        <div className="window-brand" data-tauri-drag-region>
          <span className="window-logo">A</span>
          <span>AITranslator</span>
        </div>
        <div className="window-drag-space" data-tauri-drag-region />
        <div className="window-status" data-tauri-drag-region>
          <span /> Ready
        </div>
        <div className="window-controls">
          <button aria-label="Minimize" onClick={() => window.minimize()}>−</button>
          <button aria-label="Maximize" onClick={() => window.toggleMaximize()}>□</button>
          <button className="close" aria-label="Close" onClick={() => window.close()}>×</button>
        </div>
      </header>
      <div className="window-content">{children}</div>
    </div>
  )
}
