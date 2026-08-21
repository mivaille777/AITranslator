import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { dismissOverlay, getOverlayState } from "../api/overlay"
import { desktop } from "../desktop"
import type { OverlayPositionMode } from "../desktop"
import { dispatchOverlayCommand } from "../desktop/overlay-commands"
import {
  readOverlayPreferences,
  subscribeOverlayPreferences,
  updateOverlayPreferences,
  type OverlayPreferences,
} from "../desktop/overlay-preferences"
import {
  computeOverlayWindowSize,
  type OverlayActionPresentation,
} from "../desktop/overlay-sizing"
import { queryKeys, queryPolling } from "../shared/query/query-keys"
import OverlayQuickActions, {
  type OverlayCompletedInteraction,
} from "./OverlayQuickActions"
import OverlayHeader from "./OverlayHeader"

type MenuPosition = { x: number; y: number }
type ActionPresentationState = {
  contextId: string
  presentation: OverlayActionPresentation
}

const positionLabels: Record<OverlayPositionMode, string> = {
  mouse_follow: "Near cursor",
  custom_fixed_position: "Fixed position",
  desktop_lyrics_top: "Screen top",
  desktop_lyrics_center: "Screen center",
  desktop_lyrics_bottom: "Screen bottom",
}

export default function OverlayView() {
  const [copied, setCopied] = useState(false)
  const [preferences, setPreferences] = useState(readOverlayPreferences)
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null)
  const [actionPresentationState, setActionPresentationState] = useState<ActionPresentationState>({
    contextId: "",
    presentation: "compact",
  })
  const autoDismissTimerRef = useRef<number | null>(null)
  const lastPlacedContextRef = useRef("")
  const lastSizeKeyRef = useRef("")

  const overlayQuery = useQuery({
    queryKey: queryKeys.overlay.state,
    queryFn: getOverlayState,
    refetchInterval: queryPolling.overlayState,
    staleTime: 0,
  })

  const { mutate: dismiss } = useMutation({
    mutationFn: dismissOverlay,
    onSuccess: () => {
      void desktop.overlay.hide()
    },
  })

  const state = overlayQuery.data
  const overlayVisible = state?.visible ?? false
  const overlayContextId = state?.context_id ?? ""
  const overlayRevision = state?.revision ?? 0
  const menuOpen = menuPosition !== null
  const actionPresentation =
    actionPresentationState.contextId === overlayContextId
      ? actionPresentationState.presentation
      : "compact"
  const overlaySize = useMemo(
    () => state
      ? computeOverlayWindowSize({
          phase: state.phase,
          translatedText: state.translated_text,
          sourceText: state.source_text,
          message: state.message,
          menuOpen,
          actionPresentation,
        })
      : null,
    [actionPresentation, menuOpen, state],
  )
  const overlaySizeKey = overlaySize ? `${overlaySize.width}x${overlaySize.height}` : ""

  const cancelAutoDismiss = useCallback(() => {
    if (autoDismissTimerRef.current !== null) {
      window.clearTimeout(autoDismissTimerRef.current)
      autoDismissTimerRef.current = null
    }
  }, [])

  const scheduleAutoDismiss = useCallback((delay: number) => {
    cancelAutoDismiss()
    if (!readOverlayPreferences().smartAutoDismiss) return

    autoDismissTimerRef.current = window.setTimeout(() => {
      autoDismissTimerRef.current = null
      dismiss()
    }, delay)
  }, [cancelAutoDismiss, dismiss])

  const handleCopy = useCallback(async () => {
    if (!state?.translated_text) return
    try {
      await navigator.clipboard.writeText(state.translated_text)
      setCopied(true)
      scheduleAutoDismiss(1400)
      window.setTimeout(() => setCopied(false), 900)
    } catch {
      setCopied(false)
    }
  }, [scheduleAutoDismiss, state?.translated_text])

  useEffect(() => subscribeOverlayPreferences(setPreferences), [])

  useEffect(() => () => cancelAutoDismiss(), [cancelAutoDismiss])

  useEffect(() => {
    let disposed = false
    let unlisten: () => void = () => {}

    void desktop.overlay
      .onMoved((position) => {
        const next = updateOverlayPreferences({
          positionMode: "custom_fixed_position",
          customPosition: position,
        })
        setPreferences(next)
      })
      .then((dispose) => {
        if (disposed) dispose()
        else unlisten = dispose
      })

    return () => {
      disposed = true
      unlisten()
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function syncNativeWindow() {
      if (!overlayVisible) {
        cancelAutoDismiss()
        lastPlacedContextRef.current = ""
        lastSizeKeyRef.current = ""
        await desktop.overlay.hide()
        return
      }

      const currentPreferences = readOverlayPreferences()
      await desktop.overlay.setAlwaysOnTop(currentPreferences.alwaysOnTop)
      await desktop.overlay.setClickThrough(currentPreferences.clickThrough)

      if (overlaySize && lastSizeKeyRef.current !== overlaySizeKey) {
        await desktop.overlay.resize(overlaySize)
        lastSizeKeyRef.current = overlaySizeKey
      }

      if (lastPlacedContextRef.current !== overlayContextId) {
        cancelAutoDismiss()
        await desktop.overlay.place(
          currentPreferences.positionMode,
          currentPreferences.customPosition,
        )
        lastPlacedContextRef.current = overlayContextId
      }

      if (!cancelled) await desktop.overlay.show()
    }

    void syncNativeWindow()
    return () => {
      cancelled = true
    }
  }, [
    cancelAutoDismiss,
    overlayContextId,
    overlayRevision,
    overlaySize,
    overlaySizeKey,
    overlayVisible,
  ])

  useEffect(() => {
    if (!overlayVisible) return

    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest("input, textarea, select, [contenteditable='true']")) return

      cancelAutoDismiss()

      if (event.key === "Escape") {
        event.preventDefault()
        if (menuOpen) {
          setMenuPosition(null)
        } else if (actionPresentation !== "compact") {
          dispatchOverlayCommand("escape")
        } else {
          dismiss()
        }
        return
      }

      if (state?.phase !== "ready") return

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "c") {
        const selectedText = window.getSelection()?.toString().trim() ?? ""
        if (selectedText) return
        event.preventDefault()
        if (actionPresentation === "result") {
          dispatchOverlayCommand("copy")
        } else {
          void handleCopy()
        }
        return
      }

      if (event.ctrlKey || event.metaKey || event.altKey) return

      if (["1", "2", "3", "4"].includes(event.key)) {
        event.preventDefault()
        dispatchOverlayCommand(`action-${event.key}` as "action-1" | "action-2" | "action-3" | "action-4")
      } else if (event.key.toLowerCase() === "m") {
        event.preventDefault()
        dispatchOverlayCommand("more")
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [
    actionPresentation,
    cancelAutoDismiss,
    dismiss,
    handleCopy,
    menuOpen,
    overlayVisible,
    state?.phase,
  ])

  function handleCompletedInteraction(interaction: OverlayCompletedInteraction) {
    if (interaction === "handoff") {
      scheduleAutoDismiss(600)
    } else if (interaction === "copy") {
      scheduleAutoDismiss(1400)
    }
  }

  function handleActionPresentationChange(presentation: OverlayActionPresentation) {
    cancelAutoDismiss()
    setActionPresentationState((current) => {
      if (current.contextId === overlayContextId && current.presentation === presentation) {
        return current
      }
      return { contextId: overlayContextId, presentation }
    })
  }

  function handleContextMenu(event: ReactMouseEvent<HTMLElement>) {
    event.preventDefault()
    if (preferences.clickThrough) return

    cancelAutoDismiss()
    const width = 220
    const estimatedVisibleHeight = Math.min(344, window.innerHeight - 16)
    setMenuPosition({
      x: Math.max(8, Math.min(event.clientX, window.innerWidth - width - 8)),
      y: Math.max(
        8,
        Math.min(event.clientY, window.innerHeight - estimatedVisibleHeight - 8),
      ),
    })
  }

  async function applyPreferences(patch: Partial<OverlayPreferences>) {
    cancelAutoDismiss()
    const next = updateOverlayPreferences(patch)
    setPreferences(next)
    setMenuPosition(null)

    if ("alwaysOnTop" in patch) {
      await desktop.overlay.setAlwaysOnTop(next.alwaysOnTop)
    }
    if ("clickThrough" in patch) {
      await desktop.overlay.setClickThrough(next.clickThrough)
    }
    if ("positionMode" in patch || "customPosition" in patch) {
      await desktop.overlay.place(next.positionMode, next.customPosition)
    }
  }

  async function fixAtCurrentPosition() {
    const position = await desktop.overlay.getPosition()
    if (!position) return
    await applyPreferences({
      positionMode: "custom_fixed_position",
      customPosition: position,
    })
  }

  async function togglePositionLock() {
    if (preferences.locked) {
      await applyPreferences({ locked: false })
      return
    }

    const position = await desktop.overlay.getPosition()
    if (!position) {
      await applyPreferences({ locked: true })
      return
    }

    await applyPreferences({
      locked: true,
      positionMode: "custom_fixed_position",
      customPosition: position,
    })
  }

  if (!state?.visible) {
    return <div className="h-screen w-screen bg-transparent" />
  }

  return (
    <main
      className="ait-overlay-root h-screen w-screen overflow-hidden bg-transparent text-slate-100"
      onContextMenu={handleContextMenu}
      onPointerDown={() => {
        cancelAutoDismiss()
        setMenuPosition(null)
      }}
    >
      <section
        key={overlayContextId}
        className={`ait-overlay-shell flex h-full flex-col overflow-hidden rounded-[24px] border border-white/10 bg-slate-900 shadow-2xl ${
          preferences.positionMode === "mouse_follow" ? "ait-overlay-near-enter" : ""
        }`}
      >
        <OverlayHeader
          sourceLanguage={state.source_language}
          targetLanguage={state.target_language}
          provider={state.provider}
          locked={preferences.locked}
          dragEnabled={!preferences.locked && !preferences.clickThrough}
          onClose={() => dismiss()}
        />

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {state.phase === "loading" && (
            <div key={`loading:${overlayRevision}`} className="ait-overlay-state-enter flex min-h-16 items-center gap-3 rounded-[18px] bg-white/[0.035] px-4 py-3 text-sm text-slate-300">
              <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-slate-600 border-t-slate-200" />
              <div>
                <p className="font-medium text-slate-200">Translating</p>
                <p className="mt-0.5 text-xs text-slate-500">Preparing the latest reading selection…</p>
              </div>
            </div>
          )}

          {state.phase === "ready" && (
            <div key={`ready:${overlayRevision}`} className="ait-overlay-state-enter">
              <p className="whitespace-pre-wrap text-sm leading-6 text-slate-100">
                {state.translated_text}
              </p>
              {state.source_text && (
                <p className="mt-4 line-clamp-3 border-t border-white/10 pt-3 text-xs leading-5 text-slate-500">
                  {state.source_text}
                </p>
              )}
            </div>
          )}

          {state.phase === "error" && (
            <div key={`error:${overlayRevision}`} className="ait-overlay-state-enter rounded-[18px] border border-rose-400/20 bg-rose-400/10 px-4 py-3.5">
              <div className="flex items-start gap-3">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-rose-300/10 text-sm font-semibold text-rose-200">!</span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-rose-100">Translation unavailable</p>
                  <p className="mt-1 break-words text-xs leading-5 text-rose-200/80">
                    {state.message || "Translation failed"}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {state.phase === "ready" && (
          <OverlayQuickActions
            key={state.context_id}
            state={state}
            onPresentationChange={handleActionPresentationChange}
            onCompletedInteraction={handleCompletedInteraction}
          />
        )}

        <footer className="flex items-center justify-between border-t border-white/10 px-4 py-3">
          <span className="truncate text-[10px] text-slate-600">
            {positionLabels[preferences.positionMode]} · Esc close · right-click
          </span>
          {state.phase === "ready" && (
            <button
              type="button"
              aria-live="polite"
              title="复制当前译文 · Ctrl/Cmd+C"
              className={`ait-overlay-copy-button ait-control-motion rounded-full px-3 py-1.5 text-xs font-medium ${copied ? "is-copied" : ""}`}
              onClick={() => void handleCopy()}
            >
              {copied ? "✓ Copied" : "Copy"}
            </button>
          )}
        </footer>
      </section>

      {menuPosition && (
        <div
          data-overlay-menu
          className="ait-overlay-context-menu ait-system-popover fixed z-50 max-h-[calc(100vh-16px)] w-[220px] overflow-y-auto rounded-[16px] border border-white/10 bg-slate-800 p-1.5 text-xs shadow-2xl"
          style={{ left: menuPosition.x, top: menuPosition.y }}
          onPointerDown={(event) => event.stopPropagation()}
        >
          <MenuHeading>Position</MenuHeading>
          <MenuItem
            label="Near cursor"
            active={preferences.positionMode === "mouse_follow"}
            disabled={preferences.locked}
            onClick={() => void applyPreferences({ positionMode: "mouse_follow" })}
          />
          <MenuItem
            label="Fix here"
            active={preferences.positionMode === "custom_fixed_position"}
            disabled={preferences.locked}
            onClick={() => void fixAtCurrentPosition()}
          />
          <MenuItem
            label="Screen top"
            active={preferences.positionMode === "desktop_lyrics_top"}
            disabled={preferences.locked}
            onClick={() => void applyPreferences({ positionMode: "desktop_lyrics_top" })}
          />
          <MenuItem
            label="Screen center"
            active={preferences.positionMode === "desktop_lyrics_center"}
            disabled={preferences.locked}
            onClick={() => void applyPreferences({ positionMode: "desktop_lyrics_center" })}
          />
          <MenuItem
            label="Screen bottom"
            active={preferences.positionMode === "desktop_lyrics_bottom"}
            disabled={preferences.locked}
            onClick={() => void applyPreferences({ positionMode: "desktop_lyrics_bottom" })}
          />

          <div className="my-1 border-t border-white/10" />
          <MenuItem
            label="Always on top"
            active={preferences.alwaysOnTop}
            onClick={() => void applyPreferences({ alwaysOnTop: !preferences.alwaysOnTop })}
          />
          <MenuItem
            label="Lock position"
            active={preferences.locked}
            onClick={() => void togglePositionLock()}
          />
          <MenuItem
            label="Click-through"
            active={preferences.clickThrough}
            onClick={() => void applyPreferences({ clickThrough: !preferences.clickThrough })}
          />
          <MenuItem
            label="Smart auto-dismiss"
            active={preferences.smartAutoDismiss}
            onClick={() => void applyPreferences({ smartAutoDismiss: !preferences.smartAutoDismiss })}
          />

          <div className="my-1 border-t border-white/10" />
          <MenuHeading>Shortcuts</MenuHeading>
          <MenuShortcut label="Close / collapse" keys="Esc" />
          <MenuShortcut label="Copy active view" keys="Ctrl+C" />
          <MenuShortcut label="AI actions" keys="1–4" />
          <MenuShortcut label="More actions" keys="M" />

          <div className="my-1 border-t border-white/10" />
          <MenuItem label="Hide overlay" danger onClick={() => dismiss()} />
        </div>
      )}
    </main>
  )
}

function MenuHeading({ children }: { children: string }) {
  return (
    <p className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
      {children}
    </p>
  )
}

function MenuShortcut({ label, keys }: { label: string; keys: string }) {
  return (
    <div className="flex items-center justify-between gap-3 px-2.5 py-1.5 text-[10px] text-slate-500">
      <span>{label}</span>
      <kbd className="rounded-md border border-white/10 bg-white/[0.035] px-1.5 py-0.5 font-mono text-[9px] text-slate-400">
        {keys}
      </kbd>
    </div>
  )
}

function MenuItem({
  label,
  active = false,
  danger = false,
  disabled = false,
  onClick,
}: {
  label: string
  active?: boolean
  danger?: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      className={`ait-control-motion flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left disabled:cursor-not-allowed disabled:opacity-35 ${
        danger
          ? "text-rose-300 hover:bg-rose-400/10"
          : "text-slate-300 hover:bg-white/10 hover:text-white"
      }`}
      onClick={onClick}
    >
      <span>{label}</span>
      {active && <span className="text-emerald-400">✓</span>}
    </button>
  )
}
