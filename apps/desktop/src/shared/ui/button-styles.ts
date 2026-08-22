import { cn } from "../lib/cn"

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger"
export type ButtonSize = "xs" | "sm" | "md"

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-slate-950 text-white shadow-sm hover:bg-slate-800 disabled:bg-slate-300",
  secondary: "border border-slate-200/80 bg-white/90 text-slate-700 shadow-sm hover:border-slate-300 hover:bg-white",
  ghost: "text-slate-600 hover:bg-slate-100/90 hover:text-slate-900",
  danger: "bg-rose-50 text-rose-700 hover:bg-rose-100",
}

const sizeClasses: Record<ButtonSize, string> = {
  xs: "rounded-[11px] px-2.5 py-1.5 text-[11px]",
  sm: "rounded-[13px] px-3.5 py-2 text-xs",
  md: "rounded-[14px] px-4 py-2.5 text-sm",
}

export function buttonClassName({
  variant = "secondary",
  size = "sm",
  className,
}: {
  variant?: ButtonVariant
  size?: ButtonSize
  className?: string
} = {}): string {
  return cn(
    "ait-control-motion inline-flex items-center justify-center gap-2 font-semibold disabled:cursor-not-allowed disabled:opacity-50",
    variantClasses[variant],
    sizeClasses[size],
    className,
  )
}
