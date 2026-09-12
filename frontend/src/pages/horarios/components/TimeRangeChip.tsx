import { formatClock } from '@/utils/formatDate'

interface TimeRangeChipProps {
  startTime: string
  endTime: string
  tone: 'fixed' | 'recurring'
  /**
   * A que dia/data esta faixa pertence, ex. "15/09/2026" ou "Segunda".
   * Entra no aria-label: sem isso, duas faixas iguais em dias diferentes
   * ficam indistinguiveis para leitor de tela.
   */
  context: string
  onEdit: () => void
  onDelete: () => void
  disabled?: boolean
}

const TONE_CLASSES: Record<
  TimeRangeChipProps['tone'],
  { wrapper: string; label: string; remove: string }
> = {
  fixed: {
    wrapper: 'bg-emerald-50',
    label: 'text-emerald-700 hover:bg-emerald-100',
    remove: 'text-emerald-500 hover:text-red-600 hover:bg-emerald-100',
  },
  recurring: {
    wrapper: 'bg-brand-50',
    label: 'text-brand-700 hover:bg-brand-100',
    remove: 'text-brand-500 hover:text-red-600 hover:bg-brand-100',
  },
}

/**
 * Faixa horaria clicavel. O botao de excluir e irmao do de editar, nao aninhado:
 * button dentro de button e HTML invalido e quebra navegacao por teclado.
 */
export function TimeRangeChip({
  startTime,
  endTime,
  tone,
  context,
  onEdit,
  onDelete,
  disabled = false,
}: TimeRangeChipProps) {
  const label = `${formatClock(startTime)} - ${formatClock(endTime)}`
  const description = `${label} em ${context}`
  const classes = TONE_CLASSES[tone]

  return (
    <span className={`inline-flex items-center rounded-md ${classes.wrapper}`}>
      <button
        type="button"
        onClick={onEdit}
        disabled={disabled}
        aria-label={`Editar horário ${description}`}
        className={[
          'inline-flex min-h-[44px] items-center rounded-l-md px-2.5 text-xs font-medium',
          'transition-colors duration-150 disabled:opacity-50',
          classes.label,
        ].join(' ')}
      >
        {label}
      </button>

      <button
        type="button"
        onClick={onDelete}
        disabled={disabled}
        aria-label={`Excluir horário ${description}`}
        className={[
          'inline-flex min-h-[44px] min-w-[32px] items-center justify-center rounded-r-md pr-2.5 pl-1',
          'text-base leading-none transition-colors duration-150 disabled:opacity-50',
          classes.remove,
        ].join(' ')}
      >
        &times;
      </button>
    </span>
  )
}
