import type { ReportPeriod } from '@/services/reports.service'

const PERIODS: { value: ReportPeriod; label: string }[] = [
  { value: 'current_month', label: 'Este mês' },
  { value: 'last_3_months', label: 'Últimos 3 meses' },
  { value: 'current_year', label: 'Este ano' },
]

interface ReportsHeaderProps {
  label: string
  period: ReportPeriod
  onPeriodChange: (period: ReportPeriod) => void
}

export function ReportsHeader({ label, period, onPeriodChange }: ReportsHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Relatórios</h1>
        <p className="text-sm text-gray-400 mt-0.5">{label}</p>
      </div>

      <div className="flex rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
        {PERIODS.map((p) => (
          <button
            key={p.value}
            onClick={() => onPeriodChange(p.value)}
            className={[
              'px-4 py-2 text-sm font-medium transition-colors',
              period === p.value
                ? 'bg-brand-500 text-white'
                : 'text-gray-600 hover:bg-gray-50',
            ].join(' ')}
          >
            {p.label}
          </button>
        ))}
      </div>
    </div>
  )
}
