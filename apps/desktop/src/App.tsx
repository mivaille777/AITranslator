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
          <WorkspaceHeader workspace={workspace} />
          <OverlayPreferencesPanel />
          <BrowserReadingContextPanel workspace={workspace} />
          <TranslationWorkspace workspace={workspace} />
        </div>
      </main>
      <CompanionPanel />
    </>
  )
}

export default App
