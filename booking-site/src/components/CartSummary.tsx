import type { CartItem, ServiceArea } from '@/types'
import { formatCurrencyBRL, formatDateLong, formatDuration } from '@/utils/format'
import { getAreasForService } from '@/utils/cartTotals'

interface CartSummaryProps {
  items: CartItem[]
  serviceAreas: ServiceArea[]
  onRemove?: (serviceId: string) => void
  professionalName?: string | null
  date?: string | null
  time?: string | null
  totalDurationMinutes: number
  totalPriceCents: number
}

export function CartSummary({
  items,
  serviceAreas,
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
      {items.map((item) => {
        const availableAreas = getAreasForService(serviceAreas, item.service.id)
        const selected = availableAreas.filter((a) => item.areaIds.includes(a.area_id))
        const duration = selected.length
          ? selected.reduce((sum, a) => sum + a.duration_minutes, 0)
          : item.service.duration_minutes
        const price = selected.length
          ? selected.reduce((sum, a) => sum + (a.price_cents ?? 0), 0)
          : item.service.price_cents

        return (
          <div
            key={item.service.id}
            className="flex items-center justify-between gap-3 border-b border-ink-100 py-3 first:pt-0 last:border-0 last:pb-0"
          >
            <div>
              <p className="font-medium text-ink-900">{item.service.name}</p>
              {selected.length > 0 ? (
                <p className="text-sm text-ink-500">{selected.map((a) => a.area_name).join(', ')}</p>
              ) : null}
              <p className="text-sm text-ink-500">
                {formatDuration(duration)}
                {price != null ? ` · a partir de ${formatCurrencyBRL(price)}` : ''}
              </p>
            </div>
            {onRemove ? (
              <button
                type="button"
                onClick={() => onRemove(item.service.id)}
                aria-label={`Remover ${item.service.name}`}
                className="shrink-0 rounded-full p-2 text-ink-400 transition-colors hover:bg-danger-100 hover:text-danger-500"
              >
                ✕
              </button>
            ) : null}
          </div>
        )
      })}

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
