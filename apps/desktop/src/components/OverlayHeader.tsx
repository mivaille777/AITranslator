type OverlayHeaderProps = {
  sourceLanguage: string
  targetLanguage: string
  provider?: string
  locked: boolean
  dragEnabled: boolean
  onClose: () => void
}

export default function OverlayHeader({
  sourceLanguage,
  targetLanguage,
  provider,
  locked,
  dragEnabled,
  onClose,
}: OverlayHeaderProps) {
  return (
    <header
      className={`flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3 ${
        dragEnabled ? "cursor-move" : "cursor-default"
      }`}
      data-tauri-drag-region={dragEnabled ? "deep" : "false"}
    >
      <div className="flex min-w-0 items-center gap-3">
        <span className="ait-overlay-drag-handle select-none text-xs tracking-[-0.15em] text-slate-600">••••</span>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
            AITranslator
          </p>
          <p className="mt-1 truncate text-xs text-slate-500">
            {sourceLanguage} → {targetLanguage}
            {provider ? ` · ${provider}` : ""}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1">
        {locked && (
          <span className="rounded-md bg-white/5 px-2 py-1 text-[10px] font-medium text-slate-500">
            Locked
          </span>
        )}
        <button
          type="button"
          aria-label="Close overlay"
          title="关闭 · Esc"
          data-tauri-drag-region="false"
          className="ait-overlay-quiet-button flex h-7 w-7 items-center justify-center rounded-full text-sm text-slate-400"
          onClick={onClose}
        >
          ×
        </button>
      </div>
    </header>
  )
}
