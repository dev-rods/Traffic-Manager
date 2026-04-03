import { dateRangeLabel } from '@/utils/dateHelpers'

interface AgendaHeaderProps {
  visibleDates: string[]
  onPrev: () => void
  onNext: () => void
  onToday: () => void
  onNewAppointment: () => void
  hasPrev: boolean
  hasNext: boolean
}

export function AgendaHeader({
  visibleDates,
  onPrev,
  onNext,
  onToday,
  onNewAppointment,
  hasPrev,
  hasNext,
}: AgendaHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Agenda</h1>
        <p className="text-sm text-gray-400 mt-0.5">
          {visibleDates.length > 0
            ? dateRangeLabel(visibleDates[0], visibleDates[visibleDates.length - 1])
            : 'Nenhuma data disponivel'}
        </p>
      </div>

      <div className="flex items-center gap-3">
        {/* Navigation */}
        <div className="flex items-center rounded-lg border border-gray-200 bg-white shadow-sm">
          <button
            onClick={onPrev}
            disabled={!hasPrev}
            className="px-3 py-2.5 text-gray-400 hover:text-gray-800 hover:bg-gray-50 rounded-l-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            ‹
          </button>
          <button
            onClick={onToday}
            className="px-4 py-2.5 text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-50 border-x border-gray-200 transition-colors"
          >
            Proximas
          </button>
          <button
            onClick={onNext}
            disabled={!hasNext}
            className="px-3 py-2.5 text-gray-400 hover:text-gray-800 hover:bg-gray-50 rounded-r-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            ›
          </button>
        </div>

        {/* New appointment */}
        <button
          onClick={onNewAppointment}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-600"
        >
          + Novo agendamento
        </button>
      </div>
    </div>
  )
}
