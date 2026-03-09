import { Card, CardHeader } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { formatTime } from '@/utils/formatDate'
import { formatCurrency } from '@/utils/formatCurrency'
import type { DashboardAppointment } from '@/services/reports.service'

interface TodayAppointmentsProps {
  appointments: DashboardAppointment[]
}

const DISCOUNT_LABELS: Record<string, string> = {
  first_session: '1a sessao',
  tier_2: '2-4 areas',
  tier_3: '5+ areas',
}

export function TodayAppointments({ appointments }: TodayAppointmentsProps) {
  return (
    <Card>
      <CardHeader title="Agendamentos de hoje" subtitle={`${appointments.length} agendamentos`} />

      {appointments.length === 0 ? (
        <EmptyState
          title="Nenhum agendamento hoje"
          description="Quando novos agendamentos forem criados, eles aparecerao aqui."
        />
      ) : (
        <div className="overflow-x-auto -mx-5">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
                <th className="px-5 py-2">Horario</th>
                <th className="px-3 py-2">Paciente</th>
                <th className="px-3 py-2">Servico</th>
                <th className="px-3 py-2">Profissional</th>
                <th className="px-3 py-2">Valor</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {appointments.map((apt) => (
                <tr key={apt.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-5 py-3 font-medium text-gray-800 whitespace-nowrap">
                    {formatTime(apt.scheduled_at)}
                  </td>
                  <td className="px-3 py-3 text-gray-700">{apt.patient_name}</td>
                  <td className="px-3 py-3">
                    <span className="text-gray-700">{apt.service_name}</span>
                    {apt.areas.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {apt.areas.map((area) => (
                          <Badge key={area} variant="info">{area}</Badge>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3 text-gray-600">{apt.professional}</td>
                  <td className="px-3 py-3 whitespace-nowrap">
                    <PriceCell appointment={apt} />
                  </td>
                  <td className="px-3 py-3">
                    <StatusBadge status={apt.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function PriceCell({ appointment: apt }: { appointment: DashboardAppointment }) {
  if (apt.discount_pct === 0 || !apt.discount_reason) {
    return <span className="font-medium text-gray-800">{formatCurrency(apt.final_price_cents)}</span>
  }

  return (
    <div>
      <span className="text-gray-400 line-through text-xs">
        {formatCurrency(apt.original_price_cents)}
      </span>
      <span className="ml-1.5 font-medium text-gray-800">
        {formatCurrency(apt.final_price_cents)}
      </span>
      <p className="text-xs text-emerald-600 mt-0.5">
        -{apt.discount_pct}% {DISCOUNT_LABELS[apt.discount_reason] ?? apt.discount_reason}
      </p>
    </div>
  )
}
