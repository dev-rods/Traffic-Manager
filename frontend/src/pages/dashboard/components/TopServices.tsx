import { Card, CardHeader } from '@/components/ui/Card'
import { formatCurrency } from '@/utils/formatCurrency'
import type { ServiceStat } from '@/services/reports.service'

interface TopServicesProps {
  services: ServiceStat[]
}

export function TopServices({ services }: TopServicesProps) {
  const maxCount = Math.max(...services.map((s) => s.count), 1)

  return (
    <Card>
      <CardHeader title="Top servicos" subtitle="Este mes" />

      {services.length === 0 ? (
        <p className="text-xs text-gray-400 py-4 text-center">Sem dados no periodo.</p>
      ) : (
        <div className="space-y-3">
          {services.map((service, i) => {
            const pct = (service.count / maxCount) * 100
            return (
              <div key={service.service_id}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-gray-700">
                    <span className="text-gray-400 mr-1.5">{i + 1}.</span>
                    {service.service_name}
                  </span>
                  <span className="text-gray-400">
                    {service.count}x &middot; {formatCurrency(service.revenue_cents)}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full bg-brand-400"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}
