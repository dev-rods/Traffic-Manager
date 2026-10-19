import type { ButtonHTMLAttributes } from 'react'
import { cx } from '@/utils/cx'
import { Spinner } from './Spinner'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
  loading?: boolean
}

// Quiosque: alvos de no mínimo 64px de altura e texto grande, para tocar de
// pé, a um braço do tablet.
const VARIANTS = {
  primary: 'bg-success-500 text-surface hover:bg-success-600 active:bg-success-600',
  secondary: 'bg-muted-100 text-muted-700 hover:bg-muted-200 active:bg-muted-200',
  ghost: 'bg-transparent text-ink-600 hover:bg-ink-100 active:bg-ink-100',
}

export function Button({
  variant = 'primary',
  loading = false,
  disabled,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={cx(
        'inline-flex min-h-16 select-none items-center justify-center gap-3 rounded-2xl px-8 font-display text-lg font-semibold transition-colors duration-150',
        'disabled:cursor-not-allowed disabled:opacity-40',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-success-500',
        VARIANTS[variant],
        className
      )}
      {...props}
    >
      {loading ? <Spinner size="md" /> : null}
      {children}
    </button>
  )
}
