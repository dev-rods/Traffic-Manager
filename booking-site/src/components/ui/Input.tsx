import { forwardRef } from 'react'
import type { InputHTMLAttributes } from 'react'
import { cx } from '@/utils/cx'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, id, className, ...props },
  ref
) {
  const inputId = id ?? props.name

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label htmlFor={inputId} className="text-sm font-medium text-ink-700">
          {label}
        </label>
      ) : null}
      <input
        ref={ref}
        id={inputId}
        className={cx(
          'h-12 rounded-xl border bg-white px-4 text-base text-ink-900 placeholder:text-ink-400 outline-none transition-colors',
          'focus:border-accent-500 focus:ring-2 focus:ring-accent-100',
          error ? 'border-danger-500' : 'border-ink-200',
          className
        )}
        aria-invalid={Boolean(error)}
        {...props}
      />
      {error ? <span className="text-sm text-danger-500">{error}</span> : null}
    </div>
  )
})
