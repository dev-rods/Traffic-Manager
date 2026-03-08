import { weekRangeLabel } from '@/utils/dateHelpers'

export type ViewMode = 'day' | 'week'

interface AgendaHeaderProps {
  weekStart: string
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
  onPrev: () => void
  onNext: () => void
  onToday: () => void
  onNewAppointment: () => void
}

export function AgendaHeader({
  weekStart,
  viewMode,
  onViewModeChange,
  onPrev,
  onNext,
  onToday,
  onNewAppointment,
}: AgendaHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Agenda</h1>
        <p className="text-sm text-gray-400 mt-0.5">{weekRangeLabel(weekStart)}</p>
      </div>

      <div className="flex items-center gap-3">
        {/* View mode toggle */}
        <div className="flex rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
          <button
            onClick={() => onViewModeChange('day')}
            className={[
              'px-4 py-2 text-sm font-medium transition-colors',
              viewMode === 'day'
                ? 'bg-brand-500 text-white'
                : 'text-gray-600 hover:bg-gray-50',
            ].join(' ')}
          >
            Dia
          </button>
          <button
            onClick={() => onViewModeChange('week')}
            className={[
              'px-4 py-2 text-sm font-medium transition-colors',
              viewMode === 'week'
                ? 'bg-brand-500 text-white'
                : 'text-gray-600 hover:bg-gray-50',
            ].join(' ')}
          >
            Semana
          </button>
        </div>

        {/* Navigation */}
        <div className="flex items-center rounded-lg border border-gray-200 bg-white shadow-sm">
          <button
            onClick={onPrev}
            className="px-3 py-2 text-gray-500 hover:text-gray-800 hover:bg-gray-50 rounded-l-lg transition-colors"
          >
            ‹
          </button>
          <button
            onClick={onToday}
            className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 border-x border-gray-200 transition-colors"
          >
            Hoje
          </button>
          <button
            onClick={onNext}
            className="px-3 py-2 text-gray-500 hover:text-gray-800 hover:bg-gray-50 rounded-r-lg transition-colors"
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
