import type { ButtonHTMLAttributes } from "react"

type AITButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary"
}

export default function AITButton({
  className = "",
  variant = "secondary",
  ...props
}: AITButtonProps) {
  const style =
    variant === "primary"
      ? "bg-slate-950 text-white hover:bg-slate-800"
      : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"

  return (
    <button
      {...props}
      className={`rounded-[14px] px-4 py-2.5 text-sm font-semibold transition duration-200 hover:-translate-y-px ${style} ${className}`}
    />
  )
}
