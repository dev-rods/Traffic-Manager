import { Card } from '@/components/ui/Card'
import { formatCurrency } from '@/utils/formatCurrency'
import type { ReportSummary } from '@/services/reports.service'

interface KpiCardsProps {
  summary: ReportSummary
}

interface KpiItem {
  label: string
  value: string
  detail?: string
  color: string
}

function buildKpis(s: ReportSummary): KpiItem[] {
  return [
    {
      label: 'Agendamentos',
      value: String(s.total_appointments),
      detail: `${s.confirmation_rate}% confirmados`,
      color: 'text-brand-600',
    },
    {
      label: 'Confirmados',
      value: String(s.confirmed_appointments),
      color: 'text-emerald-600',
    },
    {
      label: 'Cancelamentos',
      value: String(s.cancelled_appointments),
      detail: `${s.cancellation_rate}% taxa`,
      color: 'text-red-500',
    },
    {
      label: 'Receita do dia',
      value: formatCurrency(s.net_revenue_cents),
      detail: s.total_discount_cents > 0
        ? `${formatCurrency(s.total_discount_cents)} em descontos`
        : undefined,
      color: 'text-gray-900',
    },
  ]
}

export function KpiCards({ summary }: KpiCardsProps) {
  const kpis = buildKpis(summary)

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {kpis.map((kpi) => (
        <Card key={kpi.label}>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{kpi.label}</p>
          <p className={`mt-1 text-2xl font-bold ${kpi.color}`}>{kpi.value}</p>
          {kpi.detail && <p className="mt-0.5 text-xs text-gray-400">{kpi.detail}</p>}
        </Card>
      ))}
    </div>
  )
}
