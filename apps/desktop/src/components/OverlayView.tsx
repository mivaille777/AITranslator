import {
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { dismissOverlay, getOverlayState } from "../api/overlay"
import { desktop } from "../desktop"
import type { DesktopPoint, OverlayPositionMode } from "../desktop"
import {
  readOverlayPreferences,
  subscribeOverlayPreferences,
  updateOverlayPreferences,
  type OverlayPreferences,
} from "../desktop/overlay-preferences"
import { computeOverlayWindowSize } from "../desktop/overlay-sizing"
import { queryKeys, queryPolling } from "../shared/query/query-keys"

type MenuPosition = { x: number; y: number }

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
  const draggingRef = useRef(false)
  const pendingMoveRef = useRef<DesktopPoint | null>(null)
  const moveIdleTimerRef = useRef<number | null>(null)
  const dragArmTimerRef = useRef<number | null>(null)
  const lastPlacedContextRef = useRef("")
  const lastSizeKeyRef = useRef("")

  const overlayQuery = useQuery({
    queryKey: queryKeys.overlay.state,
    queryFn: getOverlayState,
    refetchInterval: queryPolling.overlayState,
    staleTime: 0,
  })

  const dismissMutation = useMutation({
    mutationFn: dismissOverlay,
    onSuccess: () => {
      void desktop.overlay.hide()
    },
  })

  const state = overlayQuery.data
  const overlayVisible = state?.visible ?? false
  const overlayContextId = state?.context_id ?? ""
  const overlayRevision = state?.revision ?? 0
  const overlaySize = state
    ? computeOverlayWindowSize({
        phase: state.phase,
        translatedText: state.translated_text,
        sourceText: state.source_text,
        message: state.message,
        menuOpen: Boolean(menuPosition),
      })
    : null
  const overlaySizeKey = overlaySize ? `${overlaySize.width}x${overlaySize.height}` : ""

  useEffect(() => subscribeOverlayPreferences(setPreferences), [])

  useEffect(() => {
    let disposed = false
    let unlisten: () => void = () => {}

    void desktop.overlay
      .onMoved((position) => {
        if (!draggingRef.current) return
        pendingMoveRef.current = position

        if (dragArmTimerRef.current !== null) {
          window.clearTimeout(dragArmTimerRef.current)
          dragArmTimerRef.current = null
        }
        if (moveIdleTimerRef.current !== null) {
          window.clearTimeout(moveIdleTimerRef.current)
        }
        moveIdleTimerRef.current = window.setTimeout(() => {
          const finalPosition = pendingMoveRef.current
          if (finalPosition) {
            const next = updateOverlayPreferences({
              positionMode: "custom_fixed_position",
              customPosition: finalPosition,
            })
            setPreferences(next)
          }
          draggingRef.current = false
          pendingMoveRef.current = null
          moveIdleTimerRef.current = null
        }, 180)
      })
      .then((dispose) => {
        if (disposed) dispose()
        else unlisten = dispose
      })

    return () => {
      disposed = true
      unlisten()
      if (moveIdleTimerRef.current !== null) {
        window.clearTimeout(moveIdleTimerRef.current)
      }
      if (dragArmTimerRef.current !== null) {
        window.clearTimeout(dragArmTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function syncNativeWindow() {
      if (!overlayVisible) {
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
  }, [overlayContextId, overlayRevision, overlaySize, overlaySizeKey, overlayVisible])

  async function handleCopy() {
    if (!state?.translated_text) return
    try {
      await navigator.clipboard.writeText(state.translated_text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 900)
    } catch {
      setCopied(false)
    }
  }

  function handleDragStart(event: ReactPointerEvent<HTMLElement>) {
    if (event.button !== 0 || preferences.locked || preferences.clickThrough) return
    if ((event.target as HTMLElement).closest("button, [data-overlay-menu]")) return

    draggingRef.current = true
    pendingMoveRef.current = null
    setMenuPosition(null)

    if (dragArmTimerRef.current !== null) {
      window.clearTimeout(dragArmTimerRef.current)
    }
    dragArmTimerRef.current = window.setTimeout(() => {
      if (pendingMoveRef.current === null) {
        draggingRef.current = false
      }
      dragArmTimerRef.current = null
    }, 450)

    void desktop.overlay.startDragging()
  }

  function handleContextMenu(event: ReactMouseEvent<HTMLElement>) {
    event.preventDefault()
    if (preferences.clickThrough) return

    const width = 220
    const estimatedVisibleHeight = Math.min(244, window.innerHeight - 16)
    setMenuPosition({
      x: Math.max(8, Math.min(event.clientX, window.innerWidth - width - 8)),
      y: Math.max(
        8,
        Math.min(event.clientY, window.innerHeight - estimatedVisibleHeight - 8),
      ),
    })
  }

  async function applyPreferences(patch: Partial<OverlayPreferences>) {
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
      className="h-screen w-screen overflow-hidden bg-transparent p-2 text-slate-100"
      onContextMenu={handleContextMenu}
      onPointerDown={() => setMenuPosition(null)}
    >
      <section className="flex h-full flex-col overflow-hidden rounded-[24px] border border-white/10 bg-slate-900 shadow-2xl">
        <header
          className={`flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3 ${
            preferences.locked ? "cursor-default" : "cursor-move"
          }`}
          onPointerDown={handleDragStart}
        >
          <div className="flex min-w-0 items-center gap-3">
            <span className="select-none text-xs tracking-[-0.15em] text-slate-600">••••</span>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                AITranslator
              </p>
              <p className="mt-1 truncate text-xs text-slate-500">
                {state.source_language} → {state.target_language}
                {state.provider ? ` · ${state.provider}` : ""}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1">
            {preferences.locked && (
              <span className="rounded-md bg-white/5 px-2 py-1 text-[10px] font-medium text-slate-500">
                Locked
              </span>
            )}
            <button
              type="button"
              aria-label="Close overlay"
              className="ait-control-motion rounded-lg px-2.5 py-1.5 text-sm text-slate-400 hover:bg-white/10 hover:text-white"
              onPointerDown={(event) => event.stopPropagation()}
              onClick={() => dismissMutation.mutate()}
            >
              ×
            </button>
          </div>
        </header>

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

        <footer className="flex items-center justify-between border-t border-white/10 px-4 py-3">
          <span className="truncate text-[10px] text-slate-600">
            {positionLabels[preferences.positionMode]} · right-click for options
          </span>
          {state.phase === "ready" && (
            <button
              type="button"
              className="ait-control-motion rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-white/15"
              onClick={() => void handleCopy()}
            >
              {copied ? "Copied" : "Copy"}
            </button>
          )}
        </footer>
      </section>

      {menuPosition && (
        <div
          data-overlay-menu
          className="ait-system-popover fixed z-50 max-h-[calc(100vh-16px)] w-[220px] overflow-y-auto rounded-[16px] border border-white/10 bg-slate-800 p-1.5 text-xs shadow-2xl"
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

          <div className="my-1 border-t border-white/10" />
          <MenuItem label="Hide overlay" danger onClick={() => dismissMutation.mutate()} />
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
