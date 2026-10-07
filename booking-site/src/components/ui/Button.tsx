import { forwardRef } from 'react'
import type { ButtonHTMLAttributes } from 'react'
import { cx } from '@/utils/cx'
import { Spinner } from './Spinner'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'muted' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  loading?: boolean
}

const SIZES = {
  sm: 'h-9 px-4 text-sm',
  md: 'h-12 px-6 text-[0.95rem]',
}

// Cores fiéis ao site de referência: verde para confirmar/avançar, creme para
// "Reservar", cinza para ações neutras (Voltar / Meus agendamentos).
const VARIANTS = {
  primary: 'bg-success-500 text-white hover:bg-success-600',
  secondary: 'bg-cream-100 text-ink-900 hover:bg-cream-200',
  muted: 'bg-muted-100 text-muted-700 hover:bg-muted-200',
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
        'inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg font-display font-semibold transition-colors duration-150',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-success-500',
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
