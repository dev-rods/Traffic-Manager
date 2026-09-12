import { useState } from 'react'
import {
  useAvailabilityRules,
  useCreateAvailabilityRule,
  useUpdateAvailabilityRule,
  useDeleteAvailabilityRule,
  useAvailabilityExceptions,
  useCreateAvailabilityException,
  useDeleteAvailabilityException,
} from '@/hooks/useAvailabilityRules'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useToast } from '@/components/ui/toastContext'
import { FixedDaysSection } from './components/FixedDaysSection'
import { RecurringSection } from './components/RecurringSection'
import { ExceptionsSection } from './components/ExceptionsSection'
import { formatCalendarDate, formatClock } from '@/utils/formatDate'
import type { AvailabilityRule, AvailabilityException } from '@/types'

const DAY_NAMES = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']

/** Altura maxima das listas, em px. ~5 linhas antes de rolar. */
const SECTION_MAX_HEIGHT = 320

const INPUT_CLASSES =
  'w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500'

function errorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { data?: { message?: string } } }).response
    if (response?.data?.message) return response.data.message
  }
  return error instanceof Error ? error.message : fallback
}

export function HorariosPage() {
  const { showToast } = useToast()

  const {
    data: rulesData,
    isLoading: rulesLoading,
    isError: rulesError,
    error: rulesErr,
    refetch: refetchRules,
  } = useAvailabilityRules()
  const {
    data: exceptions,
    isLoading: excLoading,
    isError: excError,
    error: excErr,
    refetch: refetchExceptions,
  } = useAvailabilityExceptions()

  const createRule = useCreateAvailabilityRule()
  const updateRule = useUpdateAvailabilityRule()
  const deleteRule = useDeleteAvailabilityRule()
  const createException = useCreateAvailabilityException()
  const deleteException = useDeleteAvailabilityException()

  // Ids em voo: desabilitam o item sem removerem o feedback visual.
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())

  const [showAddFixedDay, setShowAddFixedDay] = useState(false)
  const [showAddRule, setShowAddRule] = useState(false)
  const [showAddException, setShowAddException] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [editingRule, setEditingRule] = useState<AvailabilityRule | null>(null)
  const [editStart, setEditStart] = useState('09:00')
  const [editEnd, setEditEnd] = useState('18:00')

  const [fixedDate, setFixedDate] = useState('')
  const [fixedStart, setFixedStart] = useState('09:00')
  const [fixedEnd, setFixedEnd] = useState('18:00')

  const [ruleDow, setRuleDow] = useState(1)
  const [ruleStart, setRuleStart] = useState('09:00')
  const [ruleEnd, setRuleEnd] = useState('18:00')

  const [excDate, setExcDate] = useState('')
  const [excType, setExcType] = useState<'BLOCKED' | 'SPECIAL_HOURS'>('BLOCKED')
  const [excStart, setExcStart] = useState('09:00')
  const [excEnd, setExcEnd] = useState('18:00')
  const [excReason, setExcReason] = useState('')

  const rules: AvailabilityRule[] = rulesData?.data ?? []

  const markDeleting = (id: string, active: boolean) => {
    setDeletingIds((current) => {
      const next = new Set(current)
      if (active) next.add(id)
      else next.delete(id)
      return next
    })
  }

  /** Recria a regra excluida, preservando dia/data e faixa. */
  const restoreRule = async (rule: AvailabilityRule) => {
    try {
      await createRule.mutateAsync({
        ...(rule.day_of_week !== null ? { day_of_week: rule.day_of_week } : {}),
        ...(rule.rule_date !== null ? { rule_date: rule.rule_date } : {}),
        start_time: rule.start_time,
        end_time: rule.end_time,
      })
    } catch (error) {
      // Caso real: o usuario cadastrou outra regra no mesmo dia antes de desfazer,
      // e a UNIQUE(clinic_id, day_of_week) rejeita o recreate.
      showToast({
        variant: 'error',
        message: errorMessage(error, 'Não foi possível desfazer a exclusão.'),
      })
    }
  }

  const handleDeleteRule = async (rule: AvailabilityRule) => {
    markDeleting(rule.id, true)
    try {
      await deleteRule.mutateAsync(rule.id)
      showToast({
        message: `Horário de ${formatClock(rule.start_time)} excluído`,
        action: { label: 'Desfazer', onClick: () => void restoreRule(rule) },
      })
    } catch (error) {
      showToast({
        variant: 'error',
        message: errorMessage(error, 'Não foi possível excluir o horário.'),
      })
    } finally {
      markDeleting(rule.id, false)
    }
  }

  const handleDeleteManyRules = async (toDelete: AvailabilityRule[]) => {
    for (const rule of toDelete) markDeleting(rule.id, true)

    // allSettled, nao all: precisamos saber quais falharam para reportar a parcial.
    const results = await Promise.allSettled(
      toDelete.map((rule) => deleteRule.mutateAsync(rule.id)),
    )

    for (const rule of toDelete) markDeleting(rule.id, false)

    const succeeded = toDelete.filter((_, i) => results[i].status === 'fulfilled')
    const failedCount = results.length - succeeded.length

    if (failedCount > 0) {
      showToast({
        variant: 'error',
        message: `${succeeded.length} de ${results.length} horários excluídos. Os demais falharam.`,
      })
      return
    }

    const dateCount = new Set(succeeded.map((r) => r.rule_date)).size
    showToast({
      message: `${dateCount} ${dateCount === 1 ? 'data excluída' : 'datas excluídas'}`,
      action: {
        label: 'Desfazer',
        onClick: () => void Promise.all(succeeded.map((rule) => restoreRule(rule))),
      },
    })
  }

  const handleDeleteException = async (exception: AvailabilityException) => {
    markDeleting(exception.id, true)
    try {
      await deleteException.mutateAsync(exception.id)
      showToast({
        message: `Exceção de ${formatCalendarDate(exception.exception_date)} excluída`,
        action: {
          label: 'Desfazer',
          onClick: () =>
            void createException
              .mutateAsync({
                exception_date: exception.exception_date,
                exception_type: exception.exception_type,
                ...(exception.start_time && exception.end_time
                  ? { start_time: exception.start_time, end_time: exception.end_time }
                  : {}),
                ...(exception.reason ? { reason: exception.reason } : {}),
              })
              .catch((error) =>
                showToast({
                  variant: 'error',
                  message: errorMessage(error, 'Não foi possível desfazer a exclusão.'),
                }),
              ),
        },
      })
    } catch (error) {
      showToast({
        variant: 'error',
        message: errorMessage(error, 'Não foi possível excluir a exceção.'),
      })
    } finally {
      markDeleting(exception.id, false)
    }
  }

  const handleAddFixedDay = async () => {
    if (!fixedDate) return
    setFormError(null)
    try {
      await createRule.mutateAsync({
        rule_date: fixedDate,
        start_time: fixedStart,
        end_time: fixedEnd,
      })
      setFixedDate('')
      setShowAddFixedDay(false)
      showToast({ message: `${formatCalendarDate(fixedDate)} adicionado` })
    } catch (error) {
      setFormError(errorMessage(error, 'Não foi possível adicionar o dia.'))
    }
  }

  const handleAddRule = async () => {
    setFormError(null)
    try {
      await createRule.mutateAsync({
        day_of_week: ruleDow,
        start_time: ruleStart,
        end_time: ruleEnd,
      })
      setShowAddRule(false)
      showToast({ message: `Horário de ${DAY_NAMES[ruleDow]} adicionado` })
    } catch (error) {
      setFormError(errorMessage(error, 'Não foi possível adicionar o horário.'))
    }
  }

  const handleAddException = async () => {
    if (!excDate) return
    setFormError(null)
    try {
      await createException.mutateAsync({
        exception_date: excDate,
        exception_type: excType,
        ...(excType === 'SPECIAL_HOURS' ? { start_time: excStart, end_time: excEnd } : {}),
        reason: excReason || undefined,
      })
      setExcDate('')
      setExcReason('')
      setShowAddException(false)
      showToast({ message: 'Exceção adicionada' })
    } catch (error) {
      setFormError(errorMessage(error, 'Não foi possível adicionar a exceção.'))
    }
  }

  const openEditRule = (rule: AvailabilityRule) => {
    setFormError(null)
    setEditingRule(rule)
    setEditStart(formatClock(rule.start_time))
    setEditEnd(formatClock(rule.end_time))
  }

  /** PATCH direto. Antes era delete + create, que nao era atomico e travava o modal. */
  const handleEditRule = async () => {
    if (!editingRule) return
    setFormError(null)
    try {
      await updateRule.mutateAsync({
        ruleId: editingRule.id,
        payload: { start_time: editStart, end_time: editEnd },
      })
      setEditingRule(null)
      showToast({ message: 'Horário atualizado' })
    } catch (error) {
      setFormError(errorMessage(error, 'Não foi possível salvar o horário.'))
    }
  }

  const closeModals = () => {
    setFormError(null)
    setEditingRule(null)
    setShowAddFixedDay(false)
    setShowAddRule(false)
    setShowAddException(false)
  }

  if (rulesLoading) {
    return (
      <div className="p-6">
        <SkeletonTable rows={7} />
      </div>
    )
  }

  if (rulesError) {
    return (
      <div className="p-6">
        <ErrorState
          message={errorMessage(rulesErr, 'Erro ao carregar horários.')}
          onRetry={() => void refetchRules()}
        />
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">
          Horários de Funcionamento
        </h1>
        <p className="mt-1 text-sm text-gray-400">
          Defina quando a clínica está disponível para agendamentos
        </p>
      </div>

      <FixedDaysSection
        rules={rules}
        maxHeight={SECTION_MAX_HEIGHT}
        onAdd={() => {
          setFormError(null)
          setShowAddFixedDay(true)
        }}
        onEdit={openEditRule}
        onDelete={(rule) => void handleDeleteRule(rule)}
        onDeleteMany={handleDeleteManyRules}
        deletingIds={deletingIds}
      />

      <RecurringSection
        rules={rules}
        maxHeight={SECTION_MAX_HEIGHT}
        onAdd={() => {
          setFormError(null)
          setShowAddRule(true)
        }}
        onEdit={openEditRule}
        onDelete={(rule) => void handleDeleteRule(rule)}
        deletingIds={deletingIds}
      />

      <ExceptionsSection
        exceptions={exceptions ?? []}
        maxHeight={SECTION_MAX_HEIGHT}
        isLoading={excLoading}
        isError={excError}
        errorMessage={errorMessage(excErr, 'Erro ao carregar exceções.')}
        onRetry={() => void refetchExceptions()}
        onAdd={() => {
          setFormError(null)
          setShowAddException(true)
        }}
        onDelete={(exception) => void handleDeleteException(exception)}
        deletingIds={deletingIds}
      />

      {/* Editar horário */}
      <Modal open={!!editingRule} onClose={closeModals} title="Editar horário">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500">Início</label>
              <input
                type="time"
                value={editStart}
                onChange={(e) => setEditStart(e.target.value)}
                className={INPUT_CLASSES}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500">Fim</label>
              <input
                type="time"
                value={editEnd}
                onChange={(e) => setEditEnd(e.target.value)}
                className={INPUT_CLASSES}
              />
            </div>
          </div>
          {formError && <p className="text-xs text-red-600">{formError}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={closeModals}>
              Cancelar
            </Button>
            <Button onClick={() => void handleEditRule()} loading={updateRule.isPending}>
              Salvar
            </Button>
          </div>
        </div>
      </Modal>

      {/* Adicionar dia fixo */}
      <Modal open={showAddFixedDay} onClose={closeModals} title="Adicionar dia fixo">
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">Data</label>
            <input
              type="date"
              value={fixedDate}
              onChange={(e) => setFixedDate(e.target.value)}
              className={INPUT_CLASSES}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500">Início</label>
              <input
                type="time"
                value={fixedStart}
                onChange={(e) => setFixedStart(e.target.value)}
                className={INPUT_CLASSES}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500">Fim</label>
              <input
                type="time"
                value={fixedEnd}
                onChange={(e) => setFixedEnd(e.target.value)}
                className={INPUT_CLASSES}
              />
            </div>
          </div>
          {formError && <p className="text-xs text-red-600">{formError}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={closeModals}>
              Cancelar
            </Button>
            <Button
              onClick={() => void handleAddFixedDay()}
              loading={createRule.isPending}
              disabled={!fixedDate}
            >
              Adicionar
            </Button>
          </div>
        </div>
      </Modal>

      {/* Adicionar horário recorrente */}
      <Modal open={showAddRule} onClose={closeModals} title="Adicionar horário">
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">Dia da semana</label>
            <select
              value={ruleDow}
              onChange={(e) => setRuleDow(Number(e.target.value))}
              className={INPUT_CLASSES}
            >
              {DAY_NAMES.map((name, i) => (
                <option key={i} value={i}>
                  {name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500">Início</label>
              <input
                type="time"
                value={ruleStart}
                onChange={(e) => setRuleStart(e.target.value)}
                className={INPUT_CLASSES}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-gray-500">Fim</label>
              <input
                type="time"
                value={ruleEnd}
                onChange={(e) => setRuleEnd(e.target.value)}
                className={INPUT_CLASSES}
              />
            </div>
          </div>
          {formError && <p className="text-xs text-red-600">{formError}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={closeModals}>
              Cancelar
            </Button>
            <Button onClick={() => void handleAddRule()} loading={createRule.isPending}>
              Adicionar
            </Button>
          </div>
        </div>
      </Modal>

      {/* Adicionar exceção */}
      <Modal open={showAddException} onClose={closeModals} title="Adicionar exceção">
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">Data</label>
            <input
              type="date"
              value={excDate}
              onChange={(e) => setExcDate(e.target.value)}
              className={INPUT_CLASSES}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">Tipo</label>
            <div className="flex gap-2">
              {(
                [
                  { key: 'BLOCKED' as const, label: 'Dia bloqueado' },
                  { key: 'SPECIAL_HOURS' as const, label: 'Horário especial' },
                ]
              ).map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setExcType(key)}
                  className={[
                    'flex-1 rounded-lg border py-2 text-xs font-semibold transition-all duration-150',
                    excType === key
                      ? key === 'BLOCKED'
                        ? 'border-red-300 bg-red-50 text-red-700'
                        : 'border-amber-300 bg-amber-50 text-amber-700'
                      : 'border-gray-200 bg-white text-gray-400 hover:border-gray-300',
                  ].join(' ')}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {excType === 'SPECIAL_HOURS' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-500">Início</label>
                <input
                  type="time"
                  value={excStart}
                  onChange={(e) => setExcStart(e.target.value)}
                  className={INPUT_CLASSES}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-gray-500">Fim</label>
                <input
                  type="time"
                  value={excEnd}
                  onChange={(e) => setExcEnd(e.target.value)}
                  className={INPUT_CLASSES}
                />
              </div>
            </div>
          )}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500">
              Motivo (opcional)
            </label>
            <input
              type="text"
              value={excReason}
              onChange={(e) => setExcReason(e.target.value)}
              placeholder="Ex: Feriado, Manutenção..."
              className={INPUT_CLASSES}
            />
          </div>
          {formError && <p className="text-xs text-red-600">{formError}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={closeModals}>
              Cancelar
            </Button>
            <Button
              onClick={() => void handleAddException()}
              loading={createException.isPending}
              disabled={!excDate}
            >
              Adicionar
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
