export type OverlayCommand =
  | "action-1"
  | "action-2"
  | "action-3"
  | "action-4"
  | "more"
  | "copy"
  | "escape"

const OVERLAY_COMMAND_EVENT = "aitrans-overlay-command"

export function dispatchOverlayCommand(command: OverlayCommand): void {
  if (typeof window === "undefined") return
  window.dispatchEvent(new CustomEvent<OverlayCommand>(OVERLAY_COMMAND_EVENT, { detail: command }))
}

export function subscribeOverlayCommands(
  callback: (command: OverlayCommand) => void,
): () => void {
  if (typeof window === "undefined") return () => undefined

  const handler = (event: Event) => {
    callback((event as CustomEvent<OverlayCommand>).detail)
  }

  window.addEventListener(OVERLAY_COMMAND_EVENT, handler)
  return () => window.removeEventListener(OVERLAY_COMMAND_EVENT, handler)
}
