import type { ButtonHTMLAttributes } from "react"

import { cn } from "../lib/cn"

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger"
export type ButtonSize = "xs" | "sm" | "md"

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-slate-950 text-white hover:bg-slate-800 disabled:bg-slate-300",
  secondary: "border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
  danger: "bg-rose-50 text-rose-700 hover:bg-rose-100",
}

const sizeClasses: Record<ButtonSize, string> = {
  xs: "rounded-lg px-2.5 py-1.5 text-[11px]",
  sm: "rounded-xl px-3.5 py-2 text-xs",
  md: "rounded-xl px-4 py-2.5 text-sm",
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
    "inline-flex items-center justify-center gap-2 font-semibold transition disabled:cursor-not-allowed disabled:opacity-50",
    variantClasses[variant],
    sizeClasses[size],
    className,
  )
}

export function Button({
  variant = "secondary",
  size = "sm",
  className,
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: ButtonSize
}) {
  return (
    <button
      type={type}
      className={buttonClassName({ variant, size, className })}
      {...props}
    />
  )
}
