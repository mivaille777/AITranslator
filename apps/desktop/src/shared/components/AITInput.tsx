import { InputHTMLAttributes } from "react"
import "./ait-components.css"

export function AITInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="ait-input" {...props} />
}
