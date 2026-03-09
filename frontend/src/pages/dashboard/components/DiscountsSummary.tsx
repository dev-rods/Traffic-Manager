import { Card, CardHeader } from '@/components/ui/Card'
import { formatCurrency } from '@/utils/formatCurrency'
import type { DiscountStat } from '@/services/reports.service'

interface DiscountsSummaryProps {
  discounts: DiscountStat[]
}

const REASON_LABELS: Record<string, string> = {
  first_session: '1a sessao',
  tier_2: '2-4 areas',
  tier_3: '5+ areas',
}

const REASON_COLORS: Record<string, string> = {
  first_session: 'bg-emerald-500',
  tier_2: 'bg-amber-500',
  tier_3: 'bg-brand-500',
}

export function DiscountsSummary({ discounts }: DiscountsSummaryProps) {
  const totalDiscount = discounts.reduce((sum, d) => sum + d.total_discount_cents, 0)
  const totalCount = discounts.reduce((sum, d) => sum + d.count, 0)

  return (
    <Card>
      <CardHeader title="Descontos no mes" subtitle={`${totalCount} aplicados`} />

      <p className="text-2xl font-bold text-gray-900 mb-4">{formatCurrency(totalDiscount)}</p>

      <div className="space-y-3">
        {discounts.map((d) => {
          const pct = totalDiscount > 0 ? (d.total_discount_cents / totalDiscount) * 100 : 0
          return (
            <div key={d.reason}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-medium text-gray-600">
                  {REASON_LABELS[d.reason] ?? d.reason}
                </span>
                <span className="text-gray-400">
                  {d.count}x &middot; {formatCurrency(d.total_discount_cents)}
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-gray-100">
                <div
                  className={`h-full rounded-full ${REASON_COLORS[d.reason] ?? 'bg-gray-400'}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
