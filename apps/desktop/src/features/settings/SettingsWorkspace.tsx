import OverlayPreferencesPanel from "../../components/OverlayPreferencesPanel"
import TranslationProviderSelector from "../translation/TranslationProviderSelector"
import type { TranslationWorkspaceController } from "../translation/useTranslationWorkspace"
import { LocalModelManager } from "./LocalModelManager"

export default function SettingsWorkspace({
  workspace,
}: {
  workspace: TranslationWorkspaceController
}) {
  const providerDisabled =
    workspace.backendState !== "connected" ||
    workspace.providerSwitching ||
    workspace.manualTranslating ||
    workspace.autoTranslating

  return (
    <div className="space-y-4">
      <section className="ait-surface overflow-hidden">
        <div className="p-6 lg:p-7">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Translation
            </p>
            <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-950">
              Default translation provider
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Choose the provider used by manual translation, automatic reading translation, and the native overlay. This preference is saved for future app launches.
            </p>
          </div>

          <div className="mt-6 max-w-2xl">
            <TranslationProviderSelector
              value={workspace.translationProvider}
              switching={workspace.providerSwitching}
              disabled={providerDisabled}
              title="Provider"
              description="Saved to your user settings and restored when the backend starts again."
              onChange={workspace.setTranslationProvider}
            />
          </div>

          {workspace.translationError && (
            <p className="mt-4 max-w-2xl rounded-[14px] border border-rose-100 bg-rose-50 px-3.5 py-2.5 text-sm text-rose-700">
              {workspace.translationError}
            </p>
          )}
        </div>
      </section>

      <LocalModelManager />

      <OverlayPreferencesPanel />
    </div>
  )
}
