import { Navigate, Route, Routes, useLocation } from "react-router-dom"

import CompanionHandoffNavigator from "./features/companion/CompanionHandoffNavigator"
import CompanionWorkspace from "./features/companion/CompanionWorkspace"
import BrowserReadingContextPanel from "./features/reading/BrowserReadingContextPanel"
import ReadingWorkspace from "./features/reading/ReadingWorkspace"
import ResearchRoute from "./features/research/ResearchRoute"
import SettingsWorkspace from "./features/settings/SettingsWorkspace"
import TranslationWorkspace from "./features/translation/TranslationWorkspace"
import { useTranslationWorkspace } from "./features/translation/useTranslationWorkspace"
import WorkspaceShell from "./features/workspace/WorkspaceShell"
import WorkspaceRouteBoundary from "./shared/errors/WorkspaceRouteBoundary"

function App() {
  const workspace = useTranslationWorkspace()
  const location = useLocation()

  return (
    <WorkspaceShell
      backendState={workspace.backendState}
      backendService={workspace.backendService}
      providerName={workspace.providerName}
      browserStatus={workspace.browserStatus}
      browserStatusChecking={workspace.browserStatusChecking}
    >
      <CompanionHandoffNavigator />
      <div key={location.pathname} className="workspace-route-enter">
        <WorkspaceRouteBoundary>
          <Routes>
            <Route path="/" element={<Navigate to="/translation" replace />} />
            <Route
              path="/translation"
              element={(
                <div className="space-y-4">
                  <BrowserReadingContextPanel
                    browserStatus={workspace.browserStatus}
                    readingSelection={workspace.readingSelection}
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
            <Route path="/research" element={<ResearchRoute backendState={workspace.backendState} />} />
            <Route path="/settings" element={<SettingsWorkspace workspace={workspace} />} />
            <Route path="*" element={<Navigate to="/translation" replace />} />
          </Routes>
        </WorkspaceRouteBoundary>
      </div>
    </WorkspaceShell>
  )
}

export default App
