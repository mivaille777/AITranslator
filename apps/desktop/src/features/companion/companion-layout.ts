export const companionLayoutClassNames = {
  shell:
    "ait-chat-shell grid h-full min-h-0 overflow-y-auto lg:grid-cols-[220px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)_300px] xl:overflow-hidden",
  historyPanel:
    "order-1 flex min-h-[460px] flex-col border-b border-slate-200 bg-slate-50/75 p-3 text-slate-700 lg:border-b-0 lg:border-r xl:h-full xl:min-h-0 xl:order-1",
  historyScroller:
    "mt-2 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1",
  contextPanel:
    "order-3 min-h-[360px] overflow-y-auto overscroll-contain border-t border-slate-200/70 bg-slate-50/55 p-4 lg:col-span-2 xl:h-full xl:min-h-0 xl:order-3 xl:col-span-1 xl:border-l xl:border-t-0",
  chatColumn:
    "order-2 flex min-h-[560px] flex-col bg-white xl:h-full xl:min-h-0 xl:order-2",
  messageScroller:
    "min-h-0 flex-1 overflow-y-auto overscroll-contain px-6 py-5 lg:px-8 xl:px-10",
  composer:
    "shrink-0 border-t border-slate-100/80 bg-white/96 px-5 py-4 backdrop-blur-xl lg:px-8",
} as const
