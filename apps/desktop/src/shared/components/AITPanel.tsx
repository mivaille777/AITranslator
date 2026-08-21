import type { ReactNode } from "react"

type AITPanelProps = {
  children: ReactNode
  className?: string
}

export default function AITPanel({ children, className = "" }: AITPanelProps) {
  return (
    <section
      className={`rounded-[20px] border border-slate-200/70 bg-white/80 shadow-[0_12px_36px_rgba(15,23,42,0.08)] backdrop-blur-xl ${className}`}
    >
      {children}
    </section>
  )
}
