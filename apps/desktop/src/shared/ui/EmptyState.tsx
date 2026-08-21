import type { ReactNode } from "react"

import { cn } from "../lib/cn"

export function EmptyState({
  icon,
  title,
  description,
  actions,
  className,
}: {
  icon?: ReactNode
  title: string
  description: string
  actions?: ReactNode
  className?: string
}) {
  return (
    <section
      className={cn(
        "rounded-[24px] border border-slate-200/60 bg-slate-50/65 px-6 py-14 text-center",
        className,
      )}
    >
      {icon && (
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-[16px] border border-slate-200/70 bg-white text-slate-400 shadow-sm">
          {icon}
        </div>
      )}
      <p className={`${icon ? "mt-4" : ""} text-sm font-semibold tracking-tight text-slate-800`}>{title}</p>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-500">{description}</p>
      {actions && <div className="mt-5 flex flex-wrap justify-center gap-2">{actions}</div>}
    </section>
  )
}
