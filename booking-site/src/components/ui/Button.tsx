import { forwardRef } from 'react'
import type { ButtonHTMLAttributes } from 'react'
import { cx } from '@/utils/cx'
import { Spinner } from './Spinner'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  loading?: boolean
}

const SIZES = {
  sm: 'h-9 px-4 text-sm',
  md: 'h-12 px-6 text-[0.95rem]',
}

const VARIANTS = {
  primary: 'bg-ink-900 text-ink-50 hover:bg-ink-800',
  secondary: 'bg-accent-100 text-accent-700 border border-accent-200 hover:bg-accent-200',
  ghost: 'bg-transparent text-ink-700 hover:bg-ink-100',
  danger: 'bg-transparent text-danger-500 hover:bg-danger-100',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading = false, disabled, className, children, ...props },
  ref
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg font-display font-semibold transition-colors duration-150',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500',
        SIZES[size],
        VARIANTS[variant],
        className
      )}
      {...props}
    >
      {loading ? <Spinner size="sm" /> : null}
      {children}
    </button>
  )
})
