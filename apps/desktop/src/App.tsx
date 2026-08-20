import CompanionPanel from "./components/CompanionPanel"
import OverlayPreferencesPanel from "./components/OverlayPreferencesPanel"
import BrowserReadingContextPanel from "./features/reading/BrowserReadingContextPanel"
import WorkspaceHeader from "./features/system/WorkspaceHeader"
import TranslationWorkspace from "./features/translation/TranslationWorkspace"
import { useTranslationWorkspace } from "./features/translation/useTranslationWorkspace"

function App() {
  const workspace = useTranslationWorkspace()

  return (
    <>
      <main className="min-h-screen bg-slate-50 px-6 py-8 text-slate-950">
        <div className="mx-auto w-full max-w-6xl">
          <WorkspaceHeader
            backendState={workspace.backendState}
            backendService={workspace.backendService}
            providerName={workspace.providerName}
            browserStatus={workspace.browserStatus}
            browserStatusChecking={workspace.browserStatusChecking}
          />
          <OverlayPreferencesPanel />
          <BrowserReadingContextPanel
            browserStatus={workspace.browserStatus}
            browserSelection={workspace.browserSelection}
            browserPage={workspace.browserPage}
            followBrowserSelection={workspace.followBrowserSelection}
            autoTranslateSelection={workspace.autoTranslateSelection}
            autoTranslating={workspace.autoTranslating}
            onFollowBrowserSelectionChange={workspace.setFollowBrowserSelection}
            onAutoTranslateSelectionChange={workspace.setAutoTranslateSelection}
          />
          <TranslationWorkspace workspace={workspace} />
        </div>
      </main>
      <CompanionPanel />
    </>
  )
}

export default App
