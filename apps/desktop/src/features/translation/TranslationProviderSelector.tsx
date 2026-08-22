import type { TranslationProviderName } from "../../api/translation"

export interface TranslationProviderSelectorProps {
  value: TranslationProviderName
  disabled?: boolean
  switching?: boolean
  title?: string
  description?: string
  onChange: (value: TranslationProviderName) => void
}

const translationProviderOptions: Array<{
  value: TranslationProviderName
  label: string
}> = [
  { value: "google_web", label: "Google" },
  { value: "youdao_web", label: "Youdao" },
]

export default function TranslationProviderSelector({
  value,
  disabled = false,
  switching = false,
  title = "Translation provider",
  description = "Used by manual and automatic reading translations.",
  onChange,
}: TranslationProviderSelectorProps) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[16px] border border-slate-200/70 bg-slate-50/70 px-3.5 py-3">
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
          {title}
        </p>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          {switching ? "Switching provider…" : description}
        </p>
      </div>
      <div className="relative grid shrink-0 grid-cols-2 rounded-[13px] bg-slate-200/70 p-1">
        {translationProviderOptions.map((provider) => {
          const active = value === provider.value
          return (
            <button
              key={provider.value}
              type="button"
              disabled={disabled}
              aria-pressed={active}
              className={`ait-control-motion relative z-10 rounded-[10px] px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${
                active
                  ? "bg-white text-slate-950 shadow-sm"
                  : "text-slate-500 hover:text-slate-800"
              }`}
              onClick={() => onChange(provider.value)}
            >
              {provider.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
