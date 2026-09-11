import type { Professional } from '@/types'
import { cx } from '@/utils/cx'

interface ProfessionalPickerProps {
  professionals: Professional[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export function ProfessionalPicker({ professionals, selectedId, onSelect }: ProfessionalPickerProps) {
  return (
    <div className="flex flex-wrap justify-center gap-6">
      {professionals.map((prof) => {
        const selected = prof.id === selectedId
        return (
          <button
            key={prof.id}
            type="button"
            onClick={() => onSelect(prof.id)}
            className="flex flex-col items-center gap-2"
          >
            <span
              className={cx(
                'flex h-16 w-16 items-center justify-center overflow-hidden rounded-full border-2 bg-ink-100 text-lg font-display text-ink-600 transition-colors',
                selected ? 'border-accent-500' : 'border-transparent'
              )}
            >
              {prof.photo_url ? (
                <img src={prof.photo_url} alt={prof.name} className="h-full w-full object-cover" />
              ) : (
                prof.name.charAt(0).toUpperCase()
              )}
            </span>
            <span className={cx('text-sm', selected ? 'font-semibold text-ink-900' : 'text-ink-600')}>
              {prof.name}
            </span>
          </button>
        )
      })}
    </div>
  )
}
