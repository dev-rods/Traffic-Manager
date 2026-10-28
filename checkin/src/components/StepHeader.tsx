import type { ReactNode } from 'react'
import { cx } from '@/utils/cx'

interface StepHeaderProps {
  title: string
  children?: ReactNode
  // "responsive": centralizado, mas alinhado à esquerda em tela deitada e
  // larga, quando divide a tela com o QR (tela de pagamento).
  align?: 'center' | 'responsive'
}

export function StepHeader({ title, children, align = 'center' }: StepHeaderProps) {
  return (
    <div
      className={cx(
        'flex flex-col gap-2 text-center',
        align === 'responsive' && 'md:landscape:text-left'
      )}
    >
      <h1 className="font-display text-3xl font-bold text-ink-900 sm:text-4xl">{title}</h1>
      {children ? <p className="text-lg text-ink-600">{children}</p> : null}
    </div>
  )
}

export function ErrorMessage({ children }: { children: ReactNode }) {
  return (
    <p
      role="alert"
      className="rounded-2xl bg-danger-100 px-5 py-4 text-center text-base text-danger-500"
    >
      {children}
    </p>
  )
}
