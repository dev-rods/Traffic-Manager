import { Badge } from '@/components/ui/Badge'
import { formatCurrency } from '@/utils/formatCurrency'
import { formatDate } from '@/utils/formatDate'
import { formatPhone } from '@/utils/formatPhone'
import type { PatientWithStats } from '@/types'

function buildWhatsAppUrl(phone: string, name: string, availableDates: string[]): string {
  const firstName = name.split(' ')[0] || 'Ola'
  const datesText = availableDates.length > 0
    ? availableDates.map((d) => {
        const [y, m, day] = d.split('-')
        return `${day}/${m}`
      }).join(', ')
    : 'em breve'

  const message = `Oi ${firstName}! Tudo bem? 😊\n\nEstamos com novas datas disponíveis para agendamento: *${datesText}*.\n\nGostaria de agendar sua sessão? Responda aqui que te ajudamos! ✨`

  const cleanPhone = phone.replace(/\D/g, '')
  return `https://wa.me/${cleanPhone}?text=${encodeURIComponent(message)}`
}

interface PatientsTableProps {
  patients: PatientWithStats[]
  onSelect: (patient: PatientWithStats) => void
  availableDates?: string[]
}

export function PatientsTable({ patients, onSelect, availableDates = [] }: PatientsTableProps) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
            <th className="px-5 py-3">Paciente</th>
            <th className="px-3 py-3">Telefone</th>
            <th className="px-3 py-3">Visitas</th>
            <th className="px-3 py-3">Ultima visita</th>
            <th className="px-3 py-3">Proxima visita</th>
            <th className="px-3 py-3">Total gasto</th>
            <th className="px-3 py-3"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {patients.map((p: PatientWithStats) => (
            <tr key={p.id} onClick={() => onSelect(p)} className="hover:bg-gray-50/50 transition-colors cursor-pointer">
              <td className="px-5 py-3">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-brand-100 flex-shrink-0 flex items-center justify-center text-brand-700 font-bold text-xs">
                    {(p.name ?? '?')[0].toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-gray-800 truncate">
                      {p.name ?? 'Sem nome'}
                    </p>
                    {p.gender && (
                      <Badge variant="neutral">{p.gender === 'M' ? 'Masc' : 'Fem'}</Badge>
                    )}
                  </div>
                </div>
              </td>
              <td className="px-3 py-3 text-gray-600 whitespace-nowrap">{formatPhone(p.phone)}</td>
              <td className="px-3 py-3">
                <span className="font-medium text-gray-800">{p.total_visits}</span>
              </td>
              <td className="px-3 py-3 text-gray-600 whitespace-nowrap">
                {p.last_visit ? formatDate(p.last_visit) : '—'}
              </td>
              <td className="px-3 py-3 whitespace-nowrap">
                {p.next_visit ? (
                  <Badge variant="info">{formatDate(p.next_visit)}</Badge>
                ) : (
                  <span className="text-gray-400">—</span>
                )}
              </td>
              <td className="px-3 py-3 font-medium text-gray-800 whitespace-nowrap">
                {p.total_spent_cents > 0 ? formatCurrency(p.total_spent_cents) : '—'}
              </td>
              <td className="px-3 py-3">
                <a
                  href={buildWhatsAppUrl(p.phone, p.name ?? '', availableDates)}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-green-700 bg-green-50 hover:bg-green-100 transition-colors"
                  title="Enviar mensagem no WhatsApp"
                >
                  <span>💬</span> WhatsApp
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
