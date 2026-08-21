import type { TextareaHTMLAttributes } from "react"

type AITInputProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  className?: string
}

export default function AITInput({ className = "", ...props }: AITInputProps) {
  return (
    <textarea
      {...props}
      className={`w-full resize-y rounded-[16px] border border-slate-200/80 bg-slate-50/80 p-4 text-sm leading-6 text-slate-900 outline-none transition focus:border-slate-400 focus:bg-white focus:shadow-sm ${className}`}
    />
  )
}
