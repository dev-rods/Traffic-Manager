import { useDashboard } from '@/hooks/useDashboard'
import { ErrorState } from '@/components/ui/ErrorState'
import { SkeletonCard, SkeletonTable, SkeletonChart } from '@/components/ui/Skeleton'
import { KpiCards } from './components/KpiCards'
import { TodayAppointments } from './components/TodayAppointments'
import { WeeklyChart } from './components/WeeklyChart'
import { DiscountsSummary } from './components/DiscountsSummary'
import { TopServices } from './components/TopServices'

export function DashboardPage() {
  const { data, isLoading, isError, error, refetch } = useDashboard()

  if (isLoading) return <DashboardSkeleton />

  if (isError) {
    return (
      <div className="p-8">
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar dashboard.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Dashboard</h1>
        <p className="text-sm text-gray-400 mt-0.5">Visao geral do dia</p>
      </div>

      <KpiCards summary={data.summary} />

      <TodayAppointments appointments={data.today_appointments} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <WeeklyChart dailyCounts={data.daily_counts} />
        </div>
        <div className="space-y-6">
          <DiscountsSummary discounts={data.discount_breakdown} />
          <TopServices services={data.top_services} />
        </div>
      </div>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="p-8 space-y-6">
      <div>
        <div className="h-7 w-40 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 w-28 bg-gray-100 rounded animate-pulse mt-2" />
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
      <SkeletonTable rows={5} />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <SkeletonChart />
        </div>
        <div className="space-y-6">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    </div>
  )
}
