import { useMemo } from 'react'
import type { DayAvailability } from '@/types'
import { cx } from '@/utils/cx'
import { startOfToday, startOfWeekMonday, toISODate, weekDates } from '@/utils/weekDates'

interface WeekPickerProps {
  weekStart: Date
  onPrevWeek: () => void
  onNextWeek: () => void
  days: Record<string, DayAvailability> | undefined
  isLoading: boolean
  selectedDate: string | null
  onSelectDate: (isoDate: string) => void
}

const WEEKDAY_LABELS = ['SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SÁB', 'DOM']
const MONTH_LABELS = [
  'Janeiro',
  'Fevereiro',
  'Março',
  'Abril',
  'Maio',
  'Junho',
  'Julho',
  'Agosto',
  'Setembro',
  'Outubro',
  'Novembro',
  'Dezembro',
]

export function WeekPicker({
  weekStart,
  onPrevWeek,
  onNextWeek,
  days,
  isLoading,
  selectedDate,
  onSelectDate,
}: WeekPickerProps) {
  const today = useMemo(() => startOfToday(), [])
  const currentWeekStart = useMemo(() => startOfWeekMonday(today), [today])
  const dates = useMemo(() => weekDates(weekStart), [weekStart])

  const monthLabel = `${MONTH_LABELS[weekStart.getMonth()]} ${weekStart.getFullYear()}`
  const canGoPrev = weekStart.getTime() > currentWeekStart.getTime()

  return (
    <div>
      <p className="mb-3 text-sm font-medium capitalize text-ink-600">{monthLabel}</p>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onPrevWeek}
          disabled={!canGoPrev}
          aria-label="Semana anterior"
          className="flex h-9 w-6 shrink-0 items-center justify-center text-ink-400 transition-colors hover:text-ink-900 disabled:opacity-0"
        >
          ‹
        </button>
        <div className="grid flex-1 grid-cols-7 gap-1.5">
          {dates.map((d) => {
            const iso = toISODate(d)
            const isPast = d.getTime() < today.getTime()
            const isSelected = iso === selectedDate
            const dayInfo = days?.[iso]
            const isClosed = !isLoading && dayInfo?.status === 'CLOSED'
            const isFull = !isLoading && dayInfo?.status === 'FULL'
            const isDisabled = isPast || isClosed || isFull

            return (
              <button
                key={iso}
                type="button"
                disabled={isDisabled}
                onClick={() => onSelectDate(iso)}
                title={isFull ? 'Sem horários — dia lotado' : isClosed ? 'Sem atendimento neste dia' : undefined}
                className={cx(
                  'flex flex-col items-center gap-1 rounded-xl border py-2.5 text-sm transition-colors',
                  isDisabled && 'cursor-not-allowed border-transparent text-ink-300',
                  !isDisabled && isSelected && 'border-accent-500 bg-accent-50 font-semibold text-accent-700',
                  !isDisabled && !isSelected && 'border-ink-200 text-ink-700 hover:border-ink-400'
                )}
              >
                <span className="text-xs text-ink-400">{WEEKDAY_LABELS[(d.getDay() + 6) % 7]}</span>
                <span>{d.getDate()}</span>
                {isFull ? <span className="text-[10px] leading-none text-danger-500">lotado</span> : null}
              </button>
            )
          })}
        </div>
        <button
          type="button"
          onClick={onNextWeek}
          aria-label="Próxima semana"
          className="flex h-9 w-6 shrink-0 items-center justify-center text-ink-400 transition-colors hover:text-ink-900"
        >
          ›
        </button>
      </div>
    </div>
  )
}
