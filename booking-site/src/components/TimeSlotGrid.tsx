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
          <div key={i} className="h-10 w-20 animate-pulse rounded-full bg-ink-100" />
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
            className={cx(
              'rounded-full border px-4 py-2 text-sm font-medium transition-colors',
              selected
                ? 'border-ink-900 bg-ink-900 text-ink-50'
                : 'border-ink-200 text-ink-700 hover:border-ink-400'
            )}
          >
            {slot}
          </button>
        )
      })}
    </div>
  )
}
