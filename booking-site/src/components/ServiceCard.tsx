import type { Service } from '@/types'
import { formatCurrencyBRL, formatDuration } from '@/utils/format'
import { Button } from './ui/Button'
import { IconCalendarCheck, IconCheck, IconClock, IconMoney } from './ui/icons'

interface ServiceCardProps {
  service: Service
  inCart: boolean
  onReserve: (service: Service) => void
}

export function ServiceCard({ service, inCart, onReserve }: ServiceCardProps) {
  return (
    <div className="border-b border-ink-100 py-5 last:border-0">
      <p className="mb-2 font-bold text-ink-900">{service.name}</p>
      <div className="flex items-center gap-4">
        <div className="flex flex-1 flex-col gap-1 text-sm text-ink-500">
          <span className="inline-flex items-center gap-1.5">
            <IconClock />
            {formatDuration(service.duration_minutes)}
          </span>
          {service.price_cents != null ? (
            <span className="inline-flex items-center gap-1.5">
              <IconMoney />
              a partir de {formatCurrencyBRL(service.price_cents)}
            </span>
          ) : null}
        </div>
        <Button size="sm" variant={inCart ? 'ghost' : 'secondary'} onClick={() => onReserve(service)}>
          {inCart ? (
            <>
              <IconCheck />
              Adicionado
            </>
          ) : (
            <>
              <IconCalendarCheck />
              Reservar
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
