import { useMemo, useState } from 'react'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Button } from '@/components/ui/Button'
import { useSelection } from '@/hooks/useSelection'
import { TimeRangeChip } from './TimeRangeChip'
import { formatCalendarDate } from '@/utils/formatDate'
import type { AvailabilityRule } from '@/types'

/** Uma data com todas as suas faixas. `id` e a propria data, para o useSelection. */
interface DateGroup {
  id: string
  rules: AvailabilityRule[]
}

interface FixedDaysSectionProps {
  rules: AvailabilityRule[]
  maxHeight: number
  onAdd: () => void
  onEdit: (rule: AvailabilityRule) => void
  onDelete: (rule: AvailabilityRule) => void
  onDeleteMany: (rules: AvailabilityRule[]) => Promise<void>
  deletingIds: Set<string>
}

export function FixedDaysSection({
  rules,
  maxHeight,
  onAdd,
  onEdit,
  onDelete,
  onDeleteMany,
  deletingIds,
}: FixedDaysSectionProps) {
  const [selecting, setSelecting] = useState(false)
  const [bulkPending, setBulkPending] = useState(false)

  const dateGroups = useMemo<DateGroup[]>(() => {
    const byDate = new Map<string, AvailabilityRule[]>()
    for (const rule of rules) {
      if (rule.rule_date === null) continue
      const list = byDate.get(rule.rule_date) ?? []
      list.push(rule)
      byDate.set(rule.rule_date, list)
    }
    return [...byDate.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, dateRules]) => ({ id: date, rules: dateRules }))
  }, [rules])

  const selection = useSelection(dateGroups)

  const exitSelection = () => {
    setSelecting(false)
    selection.clear()
  }

  const handleBulkDelete = async () => {
    // Seleciona por data, mas exclui por regra: uma data pode ter varias faixas.
    const toDelete = selection.selectedItems.flatMap((group) => group.rules)
    setBulkPending(true)
    try {
      await onDeleteMany(toDelete)
      exitSelection()
    } finally {
      setBulkPending(false)
    }
  }

  return (
    <section className="mb-10">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">Dias fixos</h2>
          <p className="mt-0.5 text-xs text-gray-400">Datas específicas em que a clínica funciona</p>
        </div>

        <div className="flex items-center gap-4">
          {dateGroups.length > 0 && (
            <button
              onClick={() => (selecting ? exitSelection() : setSelecting(true))}
              className="text-xs font-semibold text-gray-500 transition-colors hover:text-gray-700"
            >
              {selecting ? 'Cancelar' : 'Selecionar'}
            </button>
          )}
          <button
            onClick={onAdd}
            className="text-xs font-semibold text-brand-600 transition-colors hover:text-brand-700"
          >
            + Adicionar dia
          </button>
        </div>
      </div>

      {selecting && (
        <div className="mb-3 flex items-center justify-between gap-4 rounded-lg bg-gray-50 px-4 py-2.5">
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={selection.pageFullySelected}
              onChange={selection.togglePage}
              aria-label="Selecionar todas as datas"
              className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500/20"
            />
            <span className="text-xs font-medium text-gray-600">
              {selection.selectedIds.size === 0
                ? 'Nenhuma data selecionada'
                : `${selection.selectedIds.size} ${selection.selectedIds.size === 1 ? 'data selecionada' : 'datas selecionadas'}`}
            </span>
          </div>
          <Button
            variant="danger"
            size="sm"
            disabled={selection.selectedIds.size === 0}
            loading={bulkPending}
            onClick={() => void handleBulkDelete()}
          >
            Excluir selecionadas
          </Button>
        </div>
      )}

      {dateGroups.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-200 py-8 text-center">
          <p className="text-sm text-gray-400">Nenhum dia fixo cadastrado</p>
          <p className="mt-1 text-xs text-gray-300">
            Adicione as datas em que a clínica estará disponível
          </p>
        </div>
      ) : (
        <ScrollArea maxHeight={maxHeight} className="rounded-lg border border-gray-200">
          <div className="divide-y divide-gray-100">
            {dateGroups.map((group) => (
              <div key={group.id} className="flex items-center gap-4 px-4 py-3">
                {selecting && (
                  <input
                    type="checkbox"
                    checked={selection.selectedIds.has(group.id)}
                    onChange={() => selection.toggle(group)}
                    aria-label={`Selecionar ${formatCalendarDate(group.id)}`}
                    className="h-4 w-4 shrink-0 rounded border-gray-300 text-brand-600 focus:ring-brand-500/20"
                  />
                )}
                <span className="w-24 shrink-0 text-sm font-medium text-gray-700">
                  {formatCalendarDate(group.id)}
                </span>
                <div className="flex flex-1 flex-wrap gap-2">
                  {group.rules.map((rule) => (
                    <TimeRangeChip
                      key={rule.id}
                      startTime={rule.start_time}
                      endTime={rule.end_time}
                      tone="fixed"
                      context={formatCalendarDate(group.id)}
                      onEdit={() => onEdit(rule)}
                      onDelete={() => onDelete(rule)}
                      disabled={selecting || deletingIds.has(rule.id)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      )}
    </section>
  )
}
