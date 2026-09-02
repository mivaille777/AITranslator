export const companionLayoutClassNames = {
  shell:
    "ait-chat-shell grid h-full min-h-0 grid-cols-1 overflow-y-auto lg:grid-cols-[220px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)_300px] xl:grid-rows-[minmax(0,1fr)] xl:overflow-hidden",
  historyPanel:
    "order-1 flex min-h-0 max-h-[380px] flex-col overflow-hidden border-b border-slate-200 bg-slate-50/75 p-3 text-slate-700 lg:max-h-[520px] lg:border-b-0 lg:border-r xl:order-1 xl:h-full xl:max-h-none",
  historyScroller:
    "ait-scroll-panel mt-2 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1",
  contextPanel:
    "ait-scroll-panel order-3 min-h-0 max-h-[420px] overflow-y-auto overscroll-contain border-t border-slate-200/70 bg-slate-50/55 p-4 lg:col-span-2 xl:order-3 xl:col-span-1 xl:h-full xl:max-h-none xl:border-l xl:border-t-0",
  chatColumn:
    "order-2 grid min-h-[520px] min-w-0 grid-rows-[minmax(0,1fr)_auto] overflow-hidden bg-white lg:min-h-[560px] xl:order-2 xl:h-full xl:min-h-0",
  messageScroller:
    "ait-chat-message-scroll min-h-0 overflow-y-scroll overscroll-contain px-6 py-5 lg:px-8 xl:px-10",
  composer:
    "ait-chat-composer sticky bottom-0 z-20 shrink-0 border-t border-slate-200/80 bg-white/98 px-5 py-4 backdrop-blur lg:px-8 xl:static",
} as const
