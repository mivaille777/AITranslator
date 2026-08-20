export type DesktopRuntime = "browser" | "tauri" | "electron"

export type OverlayPositionMode =
  | "mouse_follow"
  | "desktop_lyrics_bottom"
  | "desktop_lyrics_center"
  | "desktop_lyrics_top"
  | "custom_fixed_position"

export interface DesktopPoint {
  x: number
  y: number
}

export interface WindowAdapter {
  show(): Promise<void>
  hide(): Promise<void>
}

export interface OverlayWindowAdapter extends WindowAdapter {
  place(
    mode: OverlayPositionMode,
    customPosition?: DesktopPoint | null,
  ): Promise<DesktopPoint | null>
  startDragging(): Promise<void>
  getPosition(): Promise<DesktopPoint | null>
  setAlwaysOnTop(enabled: boolean): Promise<void>
  setClickThrough(enabled: boolean): Promise<void>
  onMoved(callback: (position: DesktopPoint) => void): Promise<() => void>
}

export interface DesktopAdapter {
  readonly runtime: DesktopRuntime
  readonly window: WindowAdapter
  readonly overlay: OverlayWindowAdapter
}
