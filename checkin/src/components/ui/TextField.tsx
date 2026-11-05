import type { InputHTMLAttributes } from 'react'
import { cx } from '@/utils/cx'

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  label: string
  value: string
  onChange: (value: string) => void
  error?: string | null
  hint?: string
}

/**
 * Campo de texto do quiosque: 64 px de altura, rótulo sempre visível e erro
 * logo abaixo. Nome e e-mail usam o teclado do iPad; os numéricos abrem o
 * teclado numérico (`inputMode`), formatados pelo chamador.
 *
 * O `<label>` contém SÓ o rótulo: erro e dica ficam fora, ligados por
 * `aria-describedby`, para o nome acessível do campo não mudar quando o erro
 * aparece.
 */
export function TextField({
  label,
  value,
  onChange,
  error,
  hint,
  id,
  className,
  ...props
}: TextFieldProps) {
  const inputId = id ?? `field-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  const messageId = `${inputId}-message`
  const message = error ?? hint
  return (
    <div className={cx('flex flex-col gap-2', className)}>
      <label htmlFor={inputId} className="font-display text-lg font-semibold text-ink-800">
        {label}
      </label>
      <input
        id={inputId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={message ? messageId : undefined}
        className={cx(
          'min-h-16 w-full rounded-2xl border-2 bg-surface px-5 text-xl text-ink-900 outline-none transition-colors duration-150 placeholder:text-ink-300',
          'focus:border-accent-400',
          error ? 'border-danger-500' : 'border-ink-200'
        )}
        {...props}
      />
      {error ? (
        <span id={messageId} role="alert" className="text-base text-danger-500">
          {error}
        </span>
      ) : hint ? (
        <span id={messageId} className="text-base text-ink-500">
          {hint}
        </span>
      ) : null}
    </div>
  )
}
