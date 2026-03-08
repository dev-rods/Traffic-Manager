import { formatCurrency } from '@/utils/formatCurrency'
import type { DiscountStat } from '@/services/reports.service'

const DISCOUNT_CONFIG: Record<string, { emoji: string; label: string; pct: string; countLabel: string }> = {
  first_session: { emoji: '🎉', label: 'Primeira sessão', pct: '20%', countLabel: 'pacientes novos' },
  tier_2: { emoji: '🌿', label: '2–4 áreas', pct: '10%', countLabel: 'agendamentos' },
  tier_3: { emoji: '🔥', label: '5+ áreas', pct: '15%', countLabel: 'agendamentos' },
}

interface DiscountBreakdownProps {
  discounts: DiscountStat[]
  label: string
  grossRevenueCents: number
}

export function DiscountBreakdown({ discounts, label }: DiscountBreakdownProps) {
  if (discounts.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-800">Descontos por tipo — {label}</h2>
        <p className="text-sm text-gray-400 mt-4">Nenhum desconto no período.</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">Descontos por tipo — {label}</h2>

      <div className="space-y-3">
        {discounts.map((d) => {
          const config = DISCOUNT_CONFIG[d.reason] ?? {
            emoji: '💰',
            label: d.reason,
            pct: '',
            countLabel: 'agendamentos',
          }

          return (
            <div
              key={d.reason}
              className="rounded-lg bg-amber-50/60 border border-amber-100 p-4 flex items-start justify-between"
            >
              <div>
                <p className="text-sm font-semibold text-gray-800">
                  {config.emoji} {config.label} {config.pct && `(${config.pct})`}
                </p>
                <p className="text-xs text-emerald-600 mt-0.5">
                  {d.count} {config.countLabel}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm font-bold text-amber-600">
                  {formatCurrency(d.total_discount_cents)}
                </p>
                <p className="text-xs text-gray-400">concedido</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
