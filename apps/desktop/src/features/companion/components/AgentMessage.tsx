import { AITPanel } from "@/shared/components/AITPanel"

export function AgentMessage({content}:{content:string}){
 return <AITPanel><strong>✦ Agent</strong><p>{content}</p><small>[Context] [Tool]</small></AITPanel>
}
