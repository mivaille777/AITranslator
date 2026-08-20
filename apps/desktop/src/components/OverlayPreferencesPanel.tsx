import { useEffect, useState } from "react"

import { desktop } from "../desktop"
import type { OverlayPositionMode } from "../desktop"
import {
  readOverlayPreferences,
  subscribeOverlayPreferences,
  updateOverlayPreferences,
  type OverlayPreferences,
} from "../desktop/overlay-preferences"

const positionOptions: Array<[OverlayPositionMode, string]> = [
  ["mouse_follow", "Follow mouse"],
  ["custom_fixed_position", "Fixed position"],
  ["desktop_lyrics_top", "Screen top"],
  ["desktop_lyrics_center", "Screen center"],
  ["desktop_lyrics_bottom", "Screen bottom"],
]

export default function OverlayPreferencesPanel() {
  const [preferences, setPreferences] = useState(readOverlayPreferences)

  useEffect(() => subscribeOverlayPreferences(setPreferences), [])

  async function apply(patch: Partial<OverlayPreferences>) {
    const next = updateOverlayPreferences(patch)
    setPreferences(next)

    if ("alwaysOnTop" in patch) {
      await desktop.overlay.setAlwaysOnTop(next.alwaysOnTop)
    }
    if ("clickThrough" in patch) {
      await desktop.overlay.setClickThrough(next.clickThrough)
    }
    if ("positionMode" in patch) {
      await desktop.overlay.place(next.positionMode, next.customPosition)
    }
  }

  async function resetInteraction() {
    const next = updateOverlayPreferences({
      positionMode: "mouse_follow",
      locked: false,
      clickThrough: false,
    })
    setPreferences(next)
    await desktop.overlay.setClickThrough(false)
    await desktop.overlay.setAlwaysOnTop(next.alwaysOnTop)
    await desktop.overlay.place(next.positionMode, next.customPosition)
  }

  return (
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-sm font-semibold">Overlay behavior</h2>
          <p className="mt-1 text-sm text-slate-500">
            Native Tauri placement and interaction settings. The main window can always disable click-through.
          </p>
        </div>

        <button
          type="button"
          className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50"
          onClick={() => void resetInteraction()}
        >
          Reset near cursor
        </button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[1.3fr_1fr_1fr_1fr]">
        <label className="grid gap-1.5 text-xs font-medium text-slate-600">
          Position mode
          <select
            className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-slate-400"
            value={preferences.positionMode}
            onChange={(event) => void apply({ positionMode: event.target.value as OverlayPositionMode })}
          >
            {positionOptions.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <PreferenceToggle
          label="Always on top"
          checked={preferences.alwaysOnTop}
          onChange={(checked) => void apply({ alwaysOnTop: checked })}
        />
        <PreferenceToggle
          label="Lock position"
          checked={preferences.locked}
          onChange={(checked) => void apply({ locked: checked })}
        />
        <PreferenceToggle
          label="Click-through"
          checked={preferences.clickThrough}
          onChange={(checked) => void apply({ clickThrough: checked })}
          warning={preferences.clickThrough}
        />
      </div>

      {preferences.clickThrough && (
        <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
          Click-through is active. The overlay ignores pointer input; disable it here to regain interaction.
        </p>
      )}
    </section>
  )
}

function PreferenceToggle({
  label,
  checked,
  onChange,
  warning = false,
}: {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
  warning?: boolean
}) {
  return (
    <label
      className={`flex min-h-[62px] items-center gap-2 rounded-xl border px-4 py-3 text-sm ${
        warning
          ? "border-amber-200 bg-amber-50 text-amber-900"
          : "border-slate-100 bg-slate-50 text-slate-700"
      }`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  )
}
