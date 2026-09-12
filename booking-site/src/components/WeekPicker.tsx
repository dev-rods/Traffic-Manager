import { useMemo, useState } from 'react'
import { cx } from '@/utils/cx'

interface WeekPickerProps {
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

function startOfToday(): Date {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}

function startOfWeekMonday(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay() // 0=Dom..6=Sáb
  const diff = day === 0 ? -6 : 1 - day
  d.setDate(d.getDate() + diff)
  d.setHours(0, 0, 0, 0)
  return d
}

function toISODate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function WeekPicker({ selectedDate, onSelectDate }: WeekPickerProps) {
  const today = useMemo(() => startOfToday(), [])
  const currentWeekStart = useMemo(() => startOfWeekMonday(today), [today])
  const [weekStart, setWeekStart] = useState<Date>(currentWeekStart)

  const days = useMemo(
    () =>
      Array.from({ length: 7 }, (_, i) => {
        const d = new Date(weekStart)
        d.setDate(d.getDate() + i)
        return d
      }),
    [weekStart]
  )

  const monthLabel = `${MONTH_LABELS[weekStart.getMonth()]} ${weekStart.getFullYear()}`
  const canGoPrev = weekStart.getTime() > currentWeekStart.getTime()

  function goPrevWeek() {
    const prev = new Date(weekStart)
    prev.setDate(prev.getDate() - 7)
    setWeekStart(prev)
  }

  function goNextWeek() {
    const next = new Date(weekStart)
    next.setDate(next.getDate() + 7)
    setWeekStart(next)
  }

  return (
    <div>
      <p className="mb-3 text-sm font-medium capitalize text-ink-600">{monthLabel}</p>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={goPrevWeek}
          disabled={!canGoPrev}
          aria-label="Semana anterior"
          className="flex h-9 w-6 shrink-0 items-center justify-center text-ink-400 transition-colors hover:text-ink-900 disabled:opacity-0"
        >
          ‹
        </button>
        <div className="grid flex-1 grid-cols-7 gap-1.5">
          {days.map((d) => {
            const iso = toISODate(d)
            const isPast = d.getTime() < today.getTime()
            const isSelected = iso === selectedDate
            return (
              <button
                key={iso}
                type="button"
                disabled={isPast}
                onClick={() => onSelectDate(iso)}
                className={cx(
                  'flex flex-col items-center gap-1 rounded-xl border py-2.5 text-sm transition-colors',
                  isPast && 'cursor-not-allowed border-transparent text-ink-300',
                  !isPast && isSelected && 'border-accent-500 bg-accent-50 font-semibold text-accent-700',
                  !isPast && !isSelected && 'border-ink-200 text-ink-700 hover:border-ink-400'
                )}
              >
                <span className="text-xs text-ink-400">{WEEKDAY_LABELS[(d.getDay() + 6) % 7]}</span>
                <span>{d.getDate()}</span>
              </button>
            )
          })}
        </div>
        <button
          type="button"
          onClick={goNextWeek}
          aria-label="Próxima semana"
          className="flex h-9 w-6 shrink-0 items-center justify-center text-ink-400 transition-colors hover:text-ink-900"
        >
          ›
        </button>
      </div>
    </div>
  )
}
