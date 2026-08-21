import type { ReactNode } from "react"
import "./ait-components.css"

export function AITPanel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`ait-panel ${className}`}>{children}</section>
}
