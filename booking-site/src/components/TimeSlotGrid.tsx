import { cx } from '@/utils/cx'

interface TimeSlotGridProps {
  slots: string[] | undefined
  isLoading: boolean
  isError: boolean
  selectedTime: string | null
  onSelect: (time: string) => void
}

export function TimeSlotGrid({ slots, isLoading, isError, selectedTime, onSelect }: TimeSlotGridProps) {
  if (isLoading) {
    return (
      <div className="flex flex-wrap gap-2" aria-label="Carregando horários">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-11 w-20 animate-pulse rounded-lg bg-ink-100" />
        ))}
      </div>
    )
  }

  if (isError) {
    return <p className="py-6 text-center text-sm text-danger-500">Não foi possível carregar os horários.</p>
  }

  if (!slots || slots.length === 0) {
    return <p className="py-6 text-center text-sm text-ink-500">Nenhum horário disponível para este dia.</p>
  }

  return (
    <div className="flex flex-wrap gap-2">
      {slots.map((slot) => {
        const selected = slot === selectedTime
        return (
          <button
            key={slot}
            type="button"
            onClick={() => onSelect(slot)}
            aria-pressed={selected}
            className={cx(
              'h-11 min-w-20 cursor-pointer rounded-lg border px-4 font-medium tabular-nums transition-colors duration-150',
              selected
                ? 'border-accent-400 bg-accent-100 font-bold text-ink-900'
                : 'border-transparent bg-ink-100 text-ink-700 hover:bg-ink-200'
            )}
          >
            {slot}
          </button>
        )
      })}
    </div>
  )
}
