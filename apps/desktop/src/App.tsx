import { Navigate, Route, Routes } from "react-router-dom"

import OverlayPreferencesPanel from "./components/OverlayPreferencesPanel"
import CompanionHandoffNavigator from "./features/companion/CompanionHandoffNavigator"
import CompanionWorkspace from "./features/companion/CompanionWorkspace"
import BrowserReadingContextPanel from "./features/reading/BrowserReadingContextPanel"
import ReadingWorkspace from "./features/reading/ReadingWorkspace"
import ResearchWorkspace from "./features/research/ResearchWorkspace"
import TranslationWorkspace from "./features/translation/TranslationWorkspace"
import { useTranslationWorkspace } from "./features/translation/useTranslationWorkspace"
import WorkspaceShell from "./features/workspace/WorkspaceShell"

function App() {
  const workspace = useTranslationWorkspace()

  return (
    <WorkspaceShell
      backendState={workspace.backendState}
      backendService={workspace.backendService}
      providerName={workspace.providerName}
      browserStatus={workspace.browserStatus}
      browserStatusChecking={workspace.browserStatusChecking}
    >
      <CompanionHandoffNavigator />
      <Routes>
        <Route path="/" element={<Navigate to="/translation" replace />} />
        <Route
          path="/translation"
          element={(
            <div className="space-y-5">
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
          )}
        />
        <Route path="/reading" element={<ReadingWorkspace workspace={workspace} />} />
        <Route path="/chat" element={<CompanionWorkspace />} />
        <Route path="/research" element={<ResearchWorkspace />} />
        <Route path="/settings" element={<OverlayPreferencesPanel />} />
        <Route path="*" element={<Navigate to="/translation" replace />} />
      </Routes>
    </WorkspaceShell>
  )
}

export default App
