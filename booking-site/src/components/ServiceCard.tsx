import type { Service } from '@/types'
import { formatCurrencyBRL, hasPrice } from '@/utils/format'
import { Button } from './ui/Button'
import { IconCalendarCheck, IconCheck, IconMoney } from './ui/icons'

interface ServiceCardProps {
  service: Service
  inCart: boolean
  onReserve: (service: Service) => void
}

export function ServiceCard({ service, inCart, onReserve }: ServiceCardProps) {
  return (
    <div className="border-b border-ink-100 py-5 last:border-0">
      <div className="flex items-center gap-4">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <p className="font-bold text-ink-900">{service.name}</p>
          {/* Duração não aparece para o cliente: é cálculo interno da agenda. */}
          {hasPrice(service.price_cents) ? (
            <span className="inline-flex items-center gap-1.5 text-sm text-ink-500">
              <IconMoney />
              a partir de {formatCurrencyBRL(service.price_cents)}
            </span>
          ) : null}
        </div>
        <Button
          size="sm"
          variant={inCart ? 'ghost' : 'secondary'}
          onClick={() => onReserve(service)}
          className="h-11 shrink-0"
        >
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
