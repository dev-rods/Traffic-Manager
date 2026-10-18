import type { ReactNode } from 'react'
import type { CartItem, ServiceArea } from '@/types'
import { formatCurrencyBRL, formatDateLong, hasPrice } from '@/utils/format'
import { getAreasForService } from '@/utils/cartTotals'
import { IconClock, IconMoney, IconTrash } from './ui/icons'

interface CartSummaryProps {
  items: CartItem[]
  serviceAreas: ServiceArea[]
  onRemove?: (serviceId: string) => void
  date?: string | null
  time?: string | null
  /** Total/desconto/valor final — vem da cotação do backend (`PriceBreakdown`). */
  price: ReactNode
}

/**
 * O que está sendo agendado. Por item, o preço de TABELA (das áreas escolhidas,
 * ou "a partir de" do serviço enquanto não há área); o total com combos e
 * desconto é o `price`, calculado pelo backend. Duração não aparece: é conta
 * interna da agenda.
 */
export function CartSummary({ items, serviceAreas, onRemove, date, time, price }: CartSummaryProps) {
  if (items.length === 0) return null

  return (
    <div className="rounded-2xl border border-ink-100 bg-surface p-5 shadow-card">
      {/* Itens num grupo próprio: `last:` só pega o último ITEM, sem borda
          dupla em cima da data/total que vêm depois. */}
      <div>
        {items.map((item) => {
          const availableAreas = getAreasForService(serviceAreas, item.service.id)
          const selected = availableAreas.filter((a) => item.areaIds.includes(a.area_id))
          const itemPrice = selected.length
            ? selected.reduce((sum, a) => sum + (a.price_cents ?? 0), 0)
            : item.service.price_cents

          return (
            <div
              key={item.service.id}
              className="flex items-center justify-between gap-3 border-b border-ink-100 py-3 first:pt-0 last:border-0 last:pb-0"
            >
              <div className="flex min-w-0 flex-col gap-1">
                <p className="font-display text-lg font-bold text-ink-900">{item.service.name}</p>
                {selected.length > 0 ? (
                  <p className="text-sm text-ink-600">{selected.map((a) => a.area_name).join(', ')}</p>
                ) : null}
                {hasPrice(itemPrice) ? (
                  <p className="inline-flex items-center gap-2 text-sm tabular-nums text-ink-600">
                    <IconMoney />
                    {selected.length > 0 ? formatCurrencyBRL(itemPrice) : `a partir de ${formatCurrencyBRL(itemPrice)}`}
                  </p>
                ) : null}
              </div>
              {onRemove ? (
                <button
                  type="button"
                  onClick={() => onRemove(item.service.id)}
                  aria-label={`Remover ${item.service.name}`}
                  className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-xl bg-danger-100 text-danger-500 transition-colors hover:bg-danger-500 hover:text-surface"
                >
                  <IconTrash className="h-5 w-5" />
                </button>
              ) : null}
            </div>
          )
        })}
      </div>

      {date && time ? (
        <p className="mt-3 inline-flex w-full items-center gap-2 border-t border-ink-100 pt-3 font-medium text-ink-800">
          <IconClock className="h-5 w-5 text-ink-600" />
          {formatDateLong(date)}, {time}
        </p>
      ) : null}

      <div className="mt-3 border-t border-ink-100 pt-3">{price}</div>
    </div>
  )
}
