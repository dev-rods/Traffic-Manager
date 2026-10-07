import type { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      <p className="font-display text-lg text-ink-800">{title}</p>
      {description ? <p className="max-w-sm text-sm text-ink-500">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  )
}
