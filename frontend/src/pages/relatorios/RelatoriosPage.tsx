import { useState } from 'react'
import { useReports } from '@/hooks/useReports'
import { ErrorState } from '@/components/ui/ErrorState'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { ReportsHeader } from './components/ReportsHeader'
import { KpiCard } from './components/KpiCard'
import { TopServicesChart } from './components/TopServicesChart'
import { DiscountBreakdown } from './components/DiscountBreakdown'
import { formatCurrency } from '@/utils/formatCurrency'
import type { ReportPeriod } from '@/services/reports.service'

const PERIOD_COMPARE_LABEL: Record<ReportPeriod, string> = {
  current_month: 'vs mês anterior',
  last_3_months: 'vs trimestre anterior',
  current_year: 'vs ano anterior',
}

export function RelatoriosPage() {
  const [period, setPeriod] = useState<ReportPeriod>('current_month')
  const { data, isLoading, isError, error, refetch } = useReports(period)

  if (isLoading) return <ReportsSkeleton />

  if (isError) {
    return (
      <div className="p-6">
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar relatórios.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  if (!data) return null

  const s = data.summary
  const compareLabel = PERIOD_COMPARE_LABEL[period]
  const discountPctOfRevenue = s.gross_revenue_cents > 0
    ? ((s.total_discount_cents / s.gross_revenue_cents) * 100).toFixed(1)
    : '0'

  return (
    <div className="p-6 space-y-6">
      <ReportsHeader
        label={data.label}
        period={period}
        onPeriodChange={setPeriod}
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard
          label="Agendamentos"
          value={String(s.total_appointments)}
          subtext={`${s.appointments_change_pct >= 0 ? '↑' : '↓'} ${Math.abs(s.appointments_change_pct)}% ${compareLabel}`}
          subtextColor={s.appointments_change_pct >= 0 ? 'text-emerald-500' : 'text-red-500'}
        />
        <KpiCard
          label="Receita bruta"
          value={formatCurrency(s.gross_revenue_cents)}
          subtext={`${s.revenue_change_pct >= 0 ? '↑' : '↓'} ${Math.abs(s.revenue_change_pct)}% ${compareLabel}`}
          subtextColor={s.revenue_change_pct >= 0 ? 'text-emerald-500' : 'text-red-500'}
        />
        <KpiCard
          label="Descontos concedidos"
          value={formatCurrency(s.total_discount_cents)}
          valueColor="text-amber-500"
          subtext={`${discountPctOfRevenue}% da receita bruta`}
          subtextColor="text-gray-400"
        />
        <KpiCard
          label="Novos pacientes"
          value={String(s.new_patients)}
          valueColor="text-emerald-500"
          subtext={`${s.patients_change_pct >= 0 ? '↑' : '↓'} ${Math.abs(s.patients_change_pct)}% ${compareLabel}`}
          subtextColor={s.patients_change_pct >= 0 ? 'text-emerald-500' : 'text-red-500'}
        />
      </div>

      {/* Bottom section */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <TopServicesChart services={data.top_services} />
        </div>
        <div className="lg:col-span-2">
          <DiscountBreakdown discounts={data.discount_breakdown} label={data.label} grossRevenueCents={s.gross_revenue_cents} />
        </div>
      </div>
    </div>
  )
}

function ReportsSkeleton() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <div className="h-7 w-40 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 w-28 bg-gray-100 rounded animate-pulse mt-2" />
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <SkeletonCard />
        </div>
        <div className="lg:col-span-2">
          <SkeletonCard />
        </div>
      </div>
    </div>
  )
}
