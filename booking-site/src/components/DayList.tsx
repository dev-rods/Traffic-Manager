import type { AvailabilityWindow, DayAvailability } from '@/types'
import { cx } from '@/utils/cx'
import { toApiPhone } from '@/utils/format'
import { ErrorState } from './ui/ErrorState'
import { IconChat } from './ui/icons'

interface DayListProps {
  days: Record<string, DayAvailability> | undefined
  bookingWindow: AvailabilityWindow | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
  selectedDate: string | null
  onSelectDate: (isoDate: string) => void
  clinicPhone: string | null
}

const WEEKDAY_SHORT = ['DOM', 'SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SÁB']
const MONTH_LONG = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
]

function parseISO(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function formatDayMonth(iso: string): string {
  const [, m, d] = iso.split('-')
  return `${d}/${m}`
}

/**
 * Só os dias com horário, dentro do mês vigente. Fechado e lotado não são
 * opção — nem aparecem. A janela (até quando, e quando o próximo mês abre)
 * vem do backend, no fuso da clínica.
 */
export function DayList({
  days,
  bookingWindow,
  isLoading,
  isError,
  onRetry,
  selectedDate,
  onSelectDate,
  clinicPhone,
}: DayListProps) {
  if (isLoading) {
    return (
      <div className="flex justify-center gap-2" aria-label="Carregando datas">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-16 w-14 animate-pulse rounded-lg bg-ink-100" />
        ))}
      </div>
    )
  }

  if (isError || !days || !bookingWindow) {
    return (
      <ErrorState message="Não foi possível carregar as datas disponíveis." onRetry={onRetry} />
    )
  }

  const available = Object.keys(days)
    .filter((iso) => days[iso].status === 'AVAILABLE')
    .sort()
  const month = MONTH_LONG[parseISO(bookingWindow.start).getMonth()]
  const nextMonth = MONTH_LONG[parseISO(bookingWindow.nextOpensOn).getMonth()]

  if (available.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-2xl border border-ink-200 bg-surface px-5 py-8 text-center">
        <p className="font-display text-lg text-ink-800">
          Não há mais horários disponíveis em {month}.
        </p>
        <p className="max-w-sm text-sm text-ink-500">
          A agenda de {nextMonth} abre em {formatDayMonth(bookingWindow.nextOpensOn)}.
        </p>
        {clinicPhone ? (
          <a
            href={`https://wa.me/${toApiPhone(clinicPhone)}`}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex h-11 items-center gap-2 rounded-lg border border-ink-200 px-5 text-sm font-medium text-ink-700 transition-colors hover:border-ink-400"
          >
            <IconChat />
            Falar com a clínica
          </a>
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-center font-medium capitalize text-ink-800">
        {month} {parseISO(bookingWindow.start).getFullYear()}
      </p>
      {/* Faixa compacta como a da referência: rola na horizontal quando não
          cabe e fica centralizada quando cabe. O mês fica no título, não em
          cada dia (PRD 025, V4). */}
      <div className="-mx-5 snap-x overflow-x-auto px-5 pb-1 [scrollbar-width:none] sm:mx-0 sm:px-0">
        <div className="mx-auto flex w-max gap-2">
          {available.map((iso) => {
            const d = parseISO(iso)
            const isSelected = iso === selectedDate
            return (
              <button
                key={iso}
                type="button"
                onClick={() => onSelectDate(iso)}
                aria-pressed={isSelected}
                aria-label={`${WEEKDAY_SHORT[d.getDay()]} ${d.getDate()} de ${MONTH_LONG[d.getMonth()]}`}
                className={cx(
                  'relative flex h-16 w-14 shrink-0 cursor-pointer snap-start flex-col items-center justify-center gap-0.5 overflow-hidden rounded-lg transition-colors duration-150',
                  isSelected
                    ? 'bg-accent-100 text-ink-900'
                    : 'bg-ink-100 text-ink-700 hover:bg-ink-200'
                )}
              >
                <span
                  className={cx(
                    'text-xs font-semibold',
                    isSelected ? 'text-accent-700' : 'text-ink-500'
                  )}
                >
                  {WEEKDAY_SHORT[d.getDay()]}
                </span>
                <span
                  className={cx('text-xl tabular-nums', isSelected ? 'font-bold' : 'font-medium')}
                >
                  {d.getDate()}
                </span>
                {isSelected ? (
                  <span aria-hidden className="absolute inset-x-0 bottom-0 h-1 bg-accent-400" />
                ) : null}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
