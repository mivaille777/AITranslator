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
        "rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center shadow-sm",
        className,
      )}
    >
      {icon && <div className="mx-auto flex w-fit text-slate-300">{icon}</div>}
      <p className="mt-3 text-sm font-semibold text-slate-800">{title}</p>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-500">{description}</p>
      {actions && <div className="mt-5 flex flex-wrap justify-center gap-2">{actions}</div>}
    </section>
  )
}
