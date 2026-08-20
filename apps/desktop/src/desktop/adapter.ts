export type DesktopRuntime = "browser" | "tauri" | "electron"

export interface WindowAdapter {
  show(): Promise<void>
  hide(): Promise<void>
}

export interface DesktopAdapter {
  readonly runtime: DesktopRuntime
  readonly window: WindowAdapter
}
