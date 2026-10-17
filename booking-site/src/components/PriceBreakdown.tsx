import type { Quote } from '@/types'
import { formatCurrencyBRL } from '@/utils/format'
import { discountLabel } from '@/utils/discountLabel'

interface PriceBreakdownProps {
  quote: Quote | undefined
  isLoading: boolean
  isError: boolean
}

function formatPct(pct: number): string {
  return `${pct.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}%`
}

/**
 * Total pela tabela, desconto aplicado e valor final — a mesma cotação que a
 * criação grava (POST /quote). Erro na cotação não bloqueia o fluxo: o backend
 * recalcula ao criar, então o cliente só deixa de ver o valor antes.
 */
export function PriceBreakdown({ quote, isLoading, isError }: PriceBreakdownProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-between" aria-label="Calculando valor">
        <span className="h-4 w-12 animate-pulse rounded bg-ink-100" />
        <span className="h-4 w-20 animate-pulse rounded bg-ink-100" />
      </div>
    )
  }

  if (isError || !quote) {
    return <p className="text-sm text-ink-500">Não foi possível calcular o valor agora.</p>
  }

  if (quote.finalPriceCents == null) {
    return (
      <div className="flex items-center justify-between text-sm font-medium text-ink-900">
        <span>Total</span>
        <span>Valor a combinar na clínica</span>
      </div>
    )
  }

  const label = discountLabel(quote.discountReason, quote.areaCount)
  const hasDiscount =
    quote.discountPct > 0 && quote.originalPriceCents != null && quote.finalPriceCents < quote.originalPriceCents

  return (
    <div className="flex flex-col gap-2 text-sm tabular-nums">
      {quote.combos.map((combo) => (
        <p key={combo.to} className="text-ink-500">
          {combo.from.join(' + ')} viraram o combo <span className="font-medium text-ink-700">{combo.to}</span>{' '}
          (economia de {formatCurrencyBRL(combo.savingsCents)})
        </p>
      ))}

      {hasDiscount ? (
        <>
          <div className="flex items-center justify-between text-ink-600">
            <span>Total</span>
            <span className="line-through decoration-ink-400">{formatCurrencyBRL(quote.originalPriceCents)}</span>
          </div>
          <div className="flex items-center justify-between gap-3 text-success-600">
            <span>
              Desconto{label ? ` · ${label}` : ''} ({formatPct(quote.discountPct)})
            </span>
            <span className="shrink-0">
              − {formatCurrencyBRL((quote.originalPriceCents ?? 0) - quote.finalPriceCents)}
            </span>
          </div>
          <div className="flex items-center justify-between border-t border-ink-100 pt-2 text-base font-semibold text-ink-900">
            <span>Valor final</span>
            <span>{formatCurrencyBRL(quote.finalPriceCents)}</span>
          </div>
        </>
      ) : (
        <div className="flex items-center justify-between text-base font-semibold text-ink-900">
          <span>Total</span>
          <span>{formatCurrencyBRL(quote.finalPriceCents)}</span>
        </div>
      )}
    </div>
  )
}
