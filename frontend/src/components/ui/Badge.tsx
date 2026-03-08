type BadgeVariant = 'success' | 'warning' | 'danger' | 'neutral' | 'info'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  className?: string
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  warning: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  danger: 'bg-red-50 text-red-700 ring-red-600/20',
  neutral: 'bg-gray-50 text-gray-600 ring-gray-500/20',
  info: 'bg-brand-50 text-brand-700 ring-brand-600/20',
}

export function Badge({ children, variant = 'neutral', className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {children}
    </span>
  )
}

const STATUS_MAP: Record<string, { label: string; variant: BadgeVariant }> = {
  confirmed: { label: 'Confirmado', variant: 'success' },
  cancelled: { label: 'Cancelado', variant: 'danger' },
  pending: { label: 'Pendente', variant: 'warning' },
}

export function StatusBadge({ status }: { status: string }) {
  const key = status.toLowerCase()
  const { label, variant } = STATUS_MAP[key] ?? { label: status, variant: 'neutral' as const }
  return <Badge variant={variant}>{label}</Badge>
}
