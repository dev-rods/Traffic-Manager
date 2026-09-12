import { ScrollArea } from '@/components/ui/ScrollArea'
import { ErrorState } from '@/components/ui/ErrorState'
import { formatCalendarDate, formatClock } from '@/utils/formatDate'
import type { AvailabilityException } from '@/types'

interface ExceptionsSectionProps {
  exceptions: AvailabilityException[]
  maxHeight: number
  isLoading: boolean
  isError: boolean
  errorMessage: string
  onRetry: () => void
  onAdd: () => void
  onDelete: (exception: AvailabilityException) => void
  deletingIds: Set<string>
}

export function ExceptionsSection({
  exceptions,
  maxHeight,
  isLoading,
  isError,
  errorMessage,
  onRetry,
  onAdd,
  onDelete,
  deletingIds,
}: ExceptionsSectionProps) {
  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">Exceções</h2>
          <p className="mt-0.5 text-xs text-gray-400">
            Feriados, dias bloqueados ou horários especiais
          </p>
        </div>
        <button
          onClick={onAdd}
          className="text-xs font-semibold text-brand-600 transition-colors hover:text-brand-700"
        >
          + Adicionar exceção
        </button>
      </div>

      {isLoading ? (
        <div className="py-4 text-xs text-gray-400">Carregando exceções...</div>
      ) : isError ? (
        // Antes, uma falha aqui renderizava o empty state: dizia "nenhuma excecao
        // cadastrada" quando na verdade a listagem tinha falhado.
        <ErrorState message={errorMessage} onRetry={onRetry} />
      ) : exceptions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-200 py-8 text-center">
          <p className="text-sm text-gray-400">Nenhuma exceção cadastrada</p>
          <p className="mt-1 text-xs text-gray-300">
            Bloqueie feriados ou defina horários especiais para datas pontuais
          </p>
        </div>
      ) : (
        <ScrollArea maxHeight={maxHeight} className="rounded-lg border border-gray-200">
          <div className="divide-y divide-gray-100">
            {exceptions.map((exc) => (
              <div key={exc.id} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="flex items-center gap-3">
                  <span
                    className={[
                      'rounded px-2 py-0.5 text-[11px] font-semibold uppercase',
                      exc.exception_type === 'BLOCKED'
                        ? 'bg-red-50 text-red-600'
                        : 'bg-amber-50 text-amber-600',
                    ].join(' ')}
                  >
                    {exc.exception_type === 'BLOCKED' ? 'Bloqueado' : 'Especial'}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-gray-800">
                      {formatCalendarDate(exc.exception_date)}
                    </p>
                    {exc.exception_type === 'SPECIAL_HOURS' && exc.start_time && exc.end_time && (
                      <p className="text-xs text-gray-400">
                        {formatClock(exc.start_time)} - {formatClock(exc.end_time)}
                      </p>
                    )}
                    {exc.reason && <p className="text-xs text-gray-400">{exc.reason}</p>}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => onDelete(exc)}
                  disabled={deletingIds.has(exc.id)}
                  aria-label={`Excluir exceção de ${formatCalendarDate(exc.exception_date)}`}
                  className={[
                    'inline-flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded-md',
                    'text-lg leading-none text-gray-300 transition-colors duration-150',
                    'hover:bg-red-50 hover:text-red-600 disabled:opacity-50',
                  ].join(' ')}
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        </ScrollArea>
      )}
    </section>
  )
}
