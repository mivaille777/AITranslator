import type { ButtonHTMLAttributes } from "react"

import {
  buttonClassName,
  type ButtonSize,
  type ButtonVariant,
} from "./button-styles"

export type { ButtonSize, ButtonVariant } from "./button-styles"

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
