import type { Service } from '@/types'
import { formatCurrencyBRL, formatDuration } from '@/utils/format'
import { Button } from './ui/Button'

interface ServiceCardProps {
  service: Service
  inCart: boolean
  onReserve: (service: Service) => void
}

export function ServiceCard({ service, inCart, onReserve }: ServiceCardProps) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-ink-100 py-5 last:border-0">
      <div className="min-w-0">
        <p className="font-medium text-ink-900">{service.name}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-500">
          <span>{formatDuration(service.duration_minutes)}</span>
          {service.price_cents != null ? (
            <span>a partir de {formatCurrencyBRL(service.price_cents)}</span>
          ) : null}
        </div>
      </div>
      <Button size="sm" variant={inCart ? 'secondary' : 'primary'} onClick={() => onReserve(service)}>
        {inCart ? 'Adicionado' : 'Reservar'}
      </Button>
    </div>
  )
}
