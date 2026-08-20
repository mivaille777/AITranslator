import type { LanguageOption } from "../../features/translation/languages"

export function LanguageSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: readonly LanguageOption[]
  onChange: (value: string) => void
}) {
  return (
    <label className="grid gap-1.5 text-xs font-medium text-slate-600">
      {label}
      <select
        className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-slate-400"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  )
}
