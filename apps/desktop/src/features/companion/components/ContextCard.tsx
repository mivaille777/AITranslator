import { BookOpenText } from "lucide-react"

import { AITPanel } from "@/shared/components/AITPanel"

export function ContextCard({
  text,
  title,
  section,
  sourceKind,
}: {
  text: string
  title: string
  section: string
  sourceKind: string
}) {
  return (
    <AITPanel className="p-5">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[12px] bg-slate-100 text-slate-700">
          <BookOpenText size={17} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Attached context</p>
          <p className="mt-1 truncate text-sm font-semibold text-slate-900">{title || "Current workspace selection"}</p>
          {section ? <p className="mt-0.5 truncate text-xs text-slate-500">{section}</p> : null}
        </div>
        {sourceKind ? (
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-medium text-slate-500">
            {sourceKind}
          </span>
        ) : null}
      </div>
      <p className="mt-4 line-clamp-4 whitespace-pre-wrap text-sm leading-6 text-slate-600">
        {text || "No reading context attached. Capture or enter source text before running the Agent."}
      </p>
    </AITPanel>
  )
}
