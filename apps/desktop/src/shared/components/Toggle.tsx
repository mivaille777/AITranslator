export function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className="ait-control-motion inline-flex min-w-[176px] items-center justify-between gap-3 rounded-[14px] border border-slate-200/70 bg-slate-50/80 px-3.5 py-2.5 text-sm font-medium text-slate-700 shadow-sm hover:border-slate-300 hover:bg-white"
      onClick={() => onChange(!checked)}
    >
      <span className="whitespace-nowrap">{label}</span>
      <span
        aria-hidden="true"
        className={`relative h-5 w-9 shrink-0 rounded-full transition-colors duration-200 ${
          checked ? "bg-slate-900" : "bg-slate-300"
        }`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ease-out ${
            checked ? "translate-x-[18px]" : "translate-x-0.5"
          }`}
        />
      </span>
    </button>
  )
}
