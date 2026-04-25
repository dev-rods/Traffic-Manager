import { Badge } from '@/components/ui/Badge'
import { WhatsAppIcon, PauseIcon, PlayIcon, TrashIcon } from '@/components/ui/Icons'
import { formatCurrency } from '@/utils/formatCurrency'
import { formatDate } from '@/utils/formatDate'
import { formatPhone } from '@/utils/formatPhone'
import type { PatientWithStats } from '@/types'

interface PatientsTableProps {
  patients: PatientWithStats[]
  onSelect: (patient: PatientWithStats) => void
  onWhatsApp: (patient: PatientWithStats) => void
  onPauseBot: (phone: string) => void
  onDelete: (patient: PatientWithStats) => void
  pausedPhones: Set<string>
  pauseLoading?: boolean
  selectedIds: Set<string>
  onToggleSelect: (id: string) => void
  onToggleAll: () => void
}

export function PatientsTable({ patients, onSelect, onWhatsApp, onPauseBot, onDelete, pausedPhones, pauseLoading, selectedIds, onToggleSelect, onToggleAll }: PatientsTableProps) {
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
            <th className="px-3 py-3">Última msg</th>
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
              <td className="px-3 py-3 text-gray-600 whitespace-nowrap">
                {p.last_message_at ? formatDate(p.last_message_at) : '—'}
              </td>
              <td className="px-3 py-3">
                <div className="flex items-center gap-1">
                  <button
                    onClick={(e) => { e.stopPropagation(); onWhatsApp(p) }}
                    className="inline-flex items-center justify-center w-9 h-9 rounded-lg text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/40"
                    title="Enviar mensagem no WhatsApp"
                    aria-label="Enviar mensagem no WhatsApp"
                  >
                    <WhatsAppIcon className="w-[18px] h-[18px]" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onPauseBot(p.phone) }}
                    disabled={pauseLoading}
                    className={[
                      'inline-flex items-center justify-center w-9 h-9 rounded-lg transition-colors cursor-pointer focus:outline-none focus-visible:ring-2',
                      pausedPhones.has(p.phone)
                        ? 'text-amber-600 bg-amber-50 hover:bg-amber-100 focus-visible:ring-amber-400/40'
                        : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100 focus-visible:ring-gray-400/40',
                      pauseLoading ? 'opacity-50 cursor-not-allowed' : '',
                    ].join(' ')}
                    title={pausedPhones.has(p.phone) ? 'Retomar bot para este paciente' : 'Pausar bot para este paciente'}
                    aria-label={pausedPhones.has(p.phone) ? 'Retomar bot' : 'Pausar bot'}
                    aria-pressed={pausedPhones.has(p.phone)}
                  >
                    {pausedPhones.has(p.phone) ? (
                      <PlayIcon className="w-[18px] h-[18px]" />
                    ) : (
                      <PauseIcon className="w-[18px] h-[18px]" />
                    )}
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(p) }}
                    className="inline-flex items-center justify-center w-9 h-9 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400/40"
                    title="Excluir paciente"
                    aria-label="Excluir paciente"
                  >
                    <TrashIcon className="w-[18px] h-[18px]" />
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
