export const companionLayoutClassNames = {
  shell:
    "ait-chat-shell grid h-full min-h-0 overflow-y-auto lg:grid-cols-[220px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)_300px] xl:grid-rows-1 xl:overflow-hidden",
  historyPanel:
    "order-1 flex min-h-[460px] flex-col border-b border-slate-200 bg-slate-50/75 p-3 text-slate-700 lg:border-b-0 lg:border-r xl:h-full xl:min-h-0 xl:order-1 xl:overflow-hidden",
  historyScroller:
    "mt-2 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1",
  contextPanel:
    "order-3 min-h-[360px] overflow-y-auto overscroll-contain border-t border-slate-200/70 bg-slate-50/55 p-4 lg:col-span-2 xl:h-full xl:min-h-0 xl:order-3 xl:col-span-1 xl:border-l xl:border-t-0",
  chatColumn:
    "order-2 grid min-h-[560px] min-w-0 grid-rows-[minmax(0,1fr)_auto] overflow-hidden bg-white xl:h-full xl:min-h-0 xl:order-2",
  messageScroller:
    "ait-chat-message-scroll min-h-0 overflow-y-scroll overscroll-contain px-6 py-5 lg:px-8 xl:px-10",
  composer:
    "ait-chat-composer relative z-20 shrink-0 border-t border-slate-200/80 bg-white px-5 py-4 lg:px-8",
} as const
