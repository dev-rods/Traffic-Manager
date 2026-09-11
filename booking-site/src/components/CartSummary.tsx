import type { Service } from '@/types'
import { formatCurrencyBRL, formatDateLong, formatDuration } from '@/utils/format'

interface CartSummaryProps {
  items: Service[]
  onRemove?: (serviceId: string) => void
  professionalName?: string | null
  date?: string | null
  time?: string | null
  totalDurationMinutes: number
  totalPriceCents: number
}

export function CartSummary({
  items,
  onRemove,
  professionalName,
  date,
  time,
  totalDurationMinutes,
  totalPriceCents,
}: CartSummaryProps) {
  if (items.length === 0) return null

  return (
    <div className="rounded-2xl border border-ink-200 bg-white p-5">
      {items.map((service) => (
        <div
          key={service.id}
          className="flex items-center justify-between gap-3 border-b border-ink-100 py-3 first:pt-0 last:border-0 last:pb-0"
        >
          <div>
            <p className="font-medium text-ink-900">{service.name}</p>
            <p className="text-sm text-ink-500">
              {formatDuration(service.duration_minutes)}
              {service.price_cents != null ? ` · a partir de ${formatCurrencyBRL(service.price_cents)}` : ''}
            </p>
          </div>
          {onRemove ? (
            <button
              type="button"
              onClick={() => onRemove(service.id)}
              aria-label={`Remover ${service.name}`}
              className="shrink-0 rounded-full p-2 text-ink-400 transition-colors hover:bg-danger-100 hover:text-danger-500"
            >
              ✕
            </button>
          ) : null}
        </div>
      ))}

      {date || professionalName ? (
        <div className="mt-3 flex flex-col gap-1 border-t border-ink-100 pt-3 text-sm text-ink-600">
          {date && time ? (
            <span>
              {formatDateLong(date)}, {time}
            </span>
          ) : null}
          {professionalName ? <span>Profissional: {professionalName}</span> : null}
        </div>
      ) : null}

      <div className="mt-3 flex items-center justify-between border-t border-ink-100 pt-3 text-sm font-medium text-ink-900">
        <span>Total</span>
        <span>
          {formatDuration(totalDurationMinutes)} · a partir de {formatCurrencyBRL(totalPriceCents)}
        </span>
      </div>
    </div>
  )
}
