export const companionLayoutClassNames = {
  shell:
    "ait-chat-shell ait-surface grid h-full min-h-0 overflow-hidden xl:grid-cols-[270px_340px_minmax(0,1fr)]",
  historyPanel:
    "flex h-full min-h-0 flex-col border-b border-slate-200 bg-[#060918] p-3 text-slate-200 xl:border-b-0 xl:border-r xl:border-white/[0.06]",
  historyScroller:
    "mt-2 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1",
  contextPanel:
    "h-full min-h-0 overflow-y-auto overscroll-contain border-b border-slate-200/70 bg-slate-50/60 p-5 xl:border-b-0 xl:border-r",
  chatColumn:
    "flex h-full min-h-0 flex-col bg-white/95",
  messageScroller:
    "min-h-0 flex-1 overflow-y-auto overscroll-contain p-5 lg:p-6",
  composer:
    "shrink-0 border-t border-slate-100/80 bg-white/90 p-4 backdrop-blur-xl",
} as const
