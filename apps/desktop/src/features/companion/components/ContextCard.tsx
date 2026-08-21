import { AITPanel } from "@/shared/components/AITPanel"

export function ContextCard({text}:{text:string}){
 return <AITPanel><div><small>Context</small><p>{text || "No context attached"}</p></div></AITPanel>
}
