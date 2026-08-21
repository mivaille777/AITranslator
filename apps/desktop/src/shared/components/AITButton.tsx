import "./ait-components.css"

export function AITButton({ label, onClick }: { label: string; onClick?: () => void }) {
  return <button className="ait-button" onClick={onClick}>{label}</button>
}
