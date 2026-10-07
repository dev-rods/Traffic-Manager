import { ScrollArea } from '@/components/ui/ScrollArea'
import { TimeRangeChip } from './TimeRangeChip'
import type { AvailabilityRule } from '@/types'

const DAY_SHORT = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
const DAY_NAMES = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']

interface RecurringSectionProps {
  rules: AvailabilityRule[]
  maxHeight: number
  onAdd: () => void
  onEdit: (rule: AvailabilityRule) => void
  onDelete: (rule: AvailabilityRule) => void
  deletingIds: Set<string>
}

export function RecurringSection({
  rules,
  maxHeight,
  onAdd,
  onEdit,
  onDelete,
  deletingIds,
}: RecurringSectionProps) {
  const rulesByDay = new Map<number, AvailabilityRule[]>()
  for (const rule of rules) {
    if (rule.day_of_week === null) continue
    const list = rulesByDay.get(rule.day_of_week) ?? []
    list.push(rule)
    rulesByDay.set(rule.day_of_week, list)
  }

  return (
    <section className="mb-10">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">Horários recorrentes</h2>
          <p className="mt-0.5 text-xs text-gray-400">Repetem toda semana no mesmo dia</p>
        </div>
        <button
          onClick={onAdd}
          className="text-xs font-semibold text-brand-600 transition-colors hover:text-brand-700"
        >
          + Adicionar faixa
        </button>
      </div>

      <ScrollArea maxHeight={maxHeight} className="rounded-lg border border-gray-200">
        <div className="divide-y divide-gray-100">
          {[0, 1, 2, 3, 4, 5, 6].map((dow) => {
            const dayRules = rulesByDay.get(dow) ?? []
            return (
              <div key={dow} className="flex items-center gap-4 px-4 py-3">
                <span className="w-16 text-sm font-medium text-gray-700">{DAY_SHORT[dow]}</span>
                <div className="flex-1">
                  {dayRules.length === 0 ? (
                    <span className="text-xs text-gray-300">Fechado</span>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {dayRules.map((rule) => (
                        <TimeRangeChip
                          key={rule.id}
                          startTime={rule.start_time}
                          endTime={rule.end_time}
                          tone="recurring"
                          context={DAY_NAMES[dow]}
                          onEdit={() => onEdit(rule)}
                          onDelete={() => onDelete(rule)}
                          disabled={deletingIds.has(rule.id)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </ScrollArea>
    </section>
  )
}
