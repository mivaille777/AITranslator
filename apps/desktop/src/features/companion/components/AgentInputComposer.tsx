import type { FormEvent } from "react"
import { ArrowUp, LoaderCircle, Square } from "lucide-react"

import { AITInput } from "@/shared/components/AITInput"

export function AgentInputComposer({
  value,
  onChange,
  onSubmit,
  onCancel,
  disabled,
  busy,
  cancelling,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  onCancel: () => void
  disabled: boolean
  busy: boolean
  cancelling: boolean
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
      {busy ? (
        <button
          type="button"
          onClick={onCancel}
          disabled={cancelling}
          aria-label="Cancel Agent"
          className="absolute bottom-3 right-3 flex h-9 w-9 items-center justify-center rounded-[12px] bg-slate-950 text-white transition hover:bg-slate-800 disabled:cursor-wait disabled:bg-slate-400"
        >
          {cancelling ? <LoaderCircle size={16} className="animate-spin" /> : <Square size={14} fill="currentColor" />}
        </button>
      ) : (
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          aria-label="Run Agent"
          className="absolute bottom-3 right-3 flex h-9 w-9 items-center justify-center rounded-[12px] bg-slate-950 text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          <ArrowUp size={16} />
        </button>
      )}
    </form>
  )
}
