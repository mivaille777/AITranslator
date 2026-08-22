import type { HTMLAttributes } from "react"

import { cn } from "../lib/cn"

export type BadgeTone = "neutral" | "success" | "info" | "warning" | "danger"

const toneClasses: Record<BadgeTone, string> = {
  neutral: "bg-slate-100 text-slate-600",
  success: "bg-emerald-50 text-emerald-700",
  info: "bg-cyan-50 text-cyan-700",
  warning: "bg-amber-50 text-amber-700",
  danger: "bg-rose-50 text-rose-700",
}

export function Badge({
  tone = "neutral",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-semibold",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  )
}
