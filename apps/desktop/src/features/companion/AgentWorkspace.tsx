import { AgentHeader } from "./components/AgentHeader"
import { ContextCard } from "./components/ContextCard"
import { AgentTrace } from "./components/AgentTrace"
import { AgentMessage } from "./components/AgentMessage"
import { AgentInputComposer } from "./components/AgentInputComposer"

export function AgentWorkspace() {
  return (
    <div className="agent-workspace">
      <AgentHeader />
      <ContextCard text="Browser selection and workspace context will appear here." />
      <AgentTrace />
      <AgentMessage content="Agent response stream will appear here." />
      <AgentInputComposer />
    </div>
  )
}

export default AgentWorkspace
