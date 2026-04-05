import { Badge } from '@/components/ui/Badge'
import { formatCurrency } from '@/utils/formatCurrency'
import { formatDate } from '@/utils/formatDate'
import { formatPhone } from '@/utils/formatPhone'
import type { PatientWithStats } from '@/types'

interface PatientsTableProps {
  patients: PatientWithStats[]
  onSelect: (patient: PatientWithStats) => void
  onWhatsApp: (patient: PatientWithStats) => void
  onPauseBot: (phone: string) => void
  pausedPhones: Set<string>
  pauseLoading?: boolean
  selectedIds: Set<string>
  onToggleSelect: (id: string) => void
  onToggleAll: () => void
}

export function PatientsTable({ patients, onSelect, onWhatsApp, onPauseBot, pausedPhones, pauseLoading, selectedIds, onToggleSelect, onToggleAll }: PatientsTableProps) {
  const allSelected = patients.length > 0 && patients.every((p) => selectedIds.has(p.id))

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-xs font-medium uppercase tracking-wide text-gray-400">
            <th className="px-3 py-3 w-10">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={onToggleAll}
                className="accent-brand-500"
              />
            </th>
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
            <tr key={p.id} className="hover:bg-gray-50/50 transition-colors">
              <td className="px-3 py-3">
                <input
                  type="checkbox"
                  checked={selectedIds.has(p.id)}
                  onChange={() => onToggleSelect(p.id)}
                  className="accent-brand-500"
                />
              </td>
              <td className="px-5 py-3 cursor-pointer" onClick={() => onSelect(p)}>
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
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={(e) => { e.stopPropagation(); onWhatsApp(p) }}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-green-700 bg-green-50 hover:bg-green-100 transition-colors cursor-pointer"
                    title="Enviar mensagem no WhatsApp"
                  >
                    <span>💬</span> WhatsApp
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onPauseBot(p.phone) }}
                    disabled={pauseLoading}
                    className={[
                      'px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer',
                      pausedPhones.has(p.phone)
                        ? 'text-amber-700 bg-amber-50 hover:bg-amber-100'
                        : 'text-gray-500 bg-gray-50 hover:bg-gray-100',
                    ].join(' ')}
                    title={pausedPhones.has(p.phone) ? 'Retomar bot para este paciente' : 'Pausar bot para este paciente'}
                  >
                    {pausedPhones.has(p.phone) ? '▶ Retomar' : '⏸ Pausar'}
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
