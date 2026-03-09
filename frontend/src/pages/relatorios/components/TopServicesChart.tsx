import { formatCurrency } from '@/utils/formatCurrency'
import type { ServiceStat } from '@/services/reports.service'

interface TopServicesChartProps {
  services: ServiceStat[]
}

export function TopServicesChart({ services }: TopServicesChartProps) {
  if (services.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-800">Serviços mais realizados</h2>
        <p className="text-sm text-gray-400 mt-4">Nenhum serviço no período selecionado.</p>
      </div>
    )
  }

  const maxCount = Math.max(...services.map((s) => s.count))

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-800 mb-5">Serviços mais realizados</h2>

      <div className="space-y-4">
        {services.map((s) => {
          const pct = maxCount > 0 ? (s.count / maxCount) * 100 : 0
          return (
            <div key={s.service_name}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-800">{s.service_name}</span>
                <span className="text-sm text-gray-400">
                  {s.count} · {formatCurrency(s.revenue_cents)}
                </span>
              </div>
              <div className="h-2.5 rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-emerald-400 transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
