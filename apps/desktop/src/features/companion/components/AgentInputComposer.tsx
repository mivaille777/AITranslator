import type { FormEvent } from "react"
import { ArrowUp, LoaderCircle } from "lucide-react"

import { AITInput } from "@/shared/components/AITInput"

export function AgentInputComposer({
  value,
  onChange,
  onSubmit,
  disabled,
  busy,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  disabled: boolean
  busy: boolean
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!disabled && value.trim()) onSubmit()
  }

  return (
    <form onSubmit={submit} className="relative">
      <AITInput
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        rows={3}
        placeholder="Ask the Agent about the current selection…"
        className="min-h-[96px] pr-14"
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault()
            if (!disabled && value.trim()) onSubmit()
          }
        }}
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        aria-label="Run Agent"
        className="absolute bottom-3 right-3 flex h-9 w-9 items-center justify-center rounded-[12px] bg-slate-950 text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {busy ? <LoaderCircle size={16} className="animate-spin" /> : <ArrowUp size={16} />}
      </button>
    </form>
  )
}
