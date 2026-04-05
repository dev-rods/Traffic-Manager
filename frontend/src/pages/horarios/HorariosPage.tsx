import { useState } from 'react'
import {
  useAvailabilityRules,
  useCreateAvailabilityRule,
  useDeleteAvailabilityRule,
  useAvailabilityExceptions,
  useCreateAvailabilityException,
} from '@/hooks/useAvailabilityRules'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { Modal } from '@/components/ui/Modal'
import type { AvailabilityRule, AvailabilityException } from '@/types'

const DAY_NAMES = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']
const DAY_SHORT = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']

function formatTime(t: string) {
  return t.slice(0, 5)
}

export function HorariosPage() {
  const { data: rulesData, isLoading: rulesLoading, isError: rulesError, error: rulesErr, refetch: refetchRules } = useAvailabilityRules()
  const { data: exceptions, isLoading: excLoading } = useAvailabilityExceptions()
  const createRule = useCreateAvailabilityRule()
  const deleteRule = useDeleteAvailabilityRule()
  const createException = useCreateAvailabilityException()

  const [showAddRule, setShowAddRule] = useState(false)
  const [showAddException, setShowAddException] = useState(false)

  // Rule form
  const [ruleDow, setRuleDow] = useState(1)
  const [ruleStart, setRuleStart] = useState('09:00')
  const [ruleEnd, setRuleEnd] = useState('18:00')

  // Exception form
  const [excDate, setExcDate] = useState('')
  const [excType, setExcType] = useState<'BLOCKED' | 'SPECIAL_HOURS'>('BLOCKED')
  const [excStart, setExcStart] = useState('09:00')
  const [excEnd, setExcEnd] = useState('18:00')
  const [excReason, setExcReason] = useState('')

  const rules: AvailabilityRule[] = rulesData?.data ?? []

  // Group rules by day_of_week
  const rulesByDay = new Map<number, AvailabilityRule[]>()
  for (const r of rules) {
    if (r.day_of_week != null) {
      const list = rulesByDay.get(r.day_of_week) ?? []
      list.push(r)
      rulesByDay.set(r.day_of_week, list)
    }
  }

  const handleAddRule = async () => {
    await createRule.mutateAsync({
      day_of_week: ruleDow,
      start_time: ruleStart,
      end_time: ruleEnd,
    })
    setShowAddRule(false)
  }

  const handleDeleteRule = async (ruleId: string) => {
    await deleteRule.mutateAsync(ruleId)
  }

  const handleAddException = async () => {
    if (!excDate) return
    await createException.mutateAsync({
      exception_date: excDate,
      exception_type: excType,
      ...(excType === 'SPECIAL_HOURS' ? { start_time: excStart, end_time: excEnd } : {}),
      reason: excReason || undefined,
    })
    setExcDate('')
    setExcReason('')
    setShowAddException(false)
  }

  if (rulesLoading) return <div className="p-6"><SkeletonTable rows={7} /></div>
  if (rulesError) {
    return (
      <div className="p-6">
        <ErrorState
          message={rulesErr instanceof Error ? rulesErr.message : 'Erro ao carregar horários.'}
          onRetry={() => refetchRules()}
        />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Horários de Funcionamento</h1>
        <p className="text-sm text-gray-400 mt-1">Defina quando a clínica está disponível para agendamentos</p>
      </div>

      {/* Weekly rules */}
      <section className="mb-10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-800">Horários recorrentes</h2>
          <button
            onClick={() => setShowAddRule(true)}
            className="text-xs font-semibold text-brand-600 hover:text-brand-700 transition-colors"
          >
            + Adicionar faixa
          </button>
        </div>

        <div className="rounded-lg border border-gray-200 divide-y divide-gray-100">
          {[0, 1, 2, 3, 4, 5, 6].map((dow) => {
            const dayRules = rulesByDay.get(dow) ?? []
            return (
              <div key={dow} className="flex items-center px-4 py-3 gap-4">
                <span className="w-16 text-sm font-medium text-gray-700">{DAY_SHORT[dow]}</span>
                <div className="flex-1">
                  {dayRules.length === 0 ? (
                    <span className="text-xs text-gray-300">Fechado</span>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {dayRules.map((r) => (
                        <span
                          key={r.id}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-brand-50 text-brand-700 text-xs font-medium"
                        >
                          {formatTime(r.start_time)} — {formatTime(r.end_time)}
                          <button
                            onClick={() => void handleDeleteRule(r.id)}
                            className="text-brand-400 hover:text-red-500 transition-colors ml-0.5"
                            title="Remover"
                          >
                            &times;
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* Exceptions */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">Exceções</h2>
            <p className="text-xs text-gray-400 mt-0.5">Feriados, dias bloqueados ou horários especiais</p>
          </div>
          <button
            onClick={() => setShowAddException(true)}
            className="text-xs font-semibold text-brand-600 hover:text-brand-700 transition-colors"
          >
            + Adicionar exceção
          </button>
        </div>

        {excLoading ? (
          <div className="text-xs text-gray-400 py-4">Carregando exceções...</div>
        ) : !exceptions || exceptions.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-200 py-8 text-center">
            <p className="text-sm text-gray-400">Nenhuma exceção cadastrada</p>
          </div>
        ) : (
          <div className="rounded-lg border border-gray-200 divide-y divide-gray-100">
            {exceptions.map((exc: AvailabilityException) => (
              <div key={exc.id} className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className={[
                    'px-2 py-0.5 rounded text-[11px] font-semibold uppercase',
                    exc.exception_type === 'BLOCKED'
                      ? 'bg-red-50 text-red-600'
                      : 'bg-amber-50 text-amber-600',
                  ].join(' ')}>
                    {exc.exception_type === 'BLOCKED' ? 'Bloqueado' : 'Especial'}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-gray-800">
                      {new Date(exc.exception_date + 'T12:00:00').toLocaleDateString('pt-BR')}
                    </p>
                    {exc.exception_type === 'SPECIAL_HOURS' && exc.start_time && exc.end_time && (
                      <p className="text-xs text-gray-400">{formatTime(exc.start_time)} — {formatTime(exc.end_time)}</p>
                    )}
                    {exc.reason && <p className="text-xs text-gray-400">{exc.reason}</p>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Add rule modal */}
      <Modal open={showAddRule} onClose={() => setShowAddRule(false)} title="Adicionar horário">
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Dia da semana</label>
            <select
              value={ruleDow}
              onChange={(e) => setRuleDow(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            >
              {DAY_NAMES.map((name, i) => (
                <option key={i} value={i}>{name}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1.5">Início</label>
              <input
                type="time"
                value={ruleStart}
                onChange={(e) => setRuleStart(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1.5">Fim</label>
              <input
                type="time"
                value={ruleEnd}
                onChange={(e) => setRuleEnd(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setShowAddRule(false)} className="px-4 py-2.5 text-sm font-medium text-gray-600 hover:text-gray-800 transition-colors">
              Cancelar
            </button>
            <button
              onClick={() => void handleAddRule()}
              disabled={createRule.isPending}
              className={[
                'px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors',
                createRule.isPending
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-gray-900 text-white hover:bg-brand-600',
              ].join(' ')}
            >
              {createRule.isPending ? 'Adicionando...' : 'Adicionar'}
            </button>
          </div>
        </div>
      </Modal>

      {/* Add exception modal */}
      <Modal open={showAddException} onClose={() => setShowAddException(false)} title="Adicionar exceção">
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Data</label>
            <input
              type="date"
              value={excDate}
              onChange={(e) => setExcDate(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Tipo</label>
            <div className="flex gap-2">
              {([
                { key: 'BLOCKED' as const, label: 'Dia bloqueado' },
                { key: 'SPECIAL_HOURS' as const, label: 'Horário especial' },
              ]).map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setExcType(key)}
                  className={[
                    'flex-1 py-2 rounded-lg text-xs font-semibold transition-all duration-150 border',
                    excType === key
                      ? key === 'BLOCKED'
                        ? 'bg-red-50 border-red-300 text-red-700'
                        : 'bg-amber-50 border-amber-300 text-amber-700'
                      : 'bg-white border-gray-200 text-gray-400 hover:border-gray-300',
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
                <label className="text-xs font-medium text-gray-500 block mb-1.5">Início</label>
                <input
                  type="time"
                  value={excStart}
                  onChange={(e) => setExcStart(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 block mb-1.5">Fim</label>
                <input
                  type="time"
                  value={excEnd}
                  onChange={(e) => setExcEnd(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
                />
              </div>
            </div>
          )}
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1.5">Motivo (opcional)</label>
            <input
              type="text"
              value={excReason}
              onChange={(e) => setExcReason(e.target.value)}
              placeholder="Ex: Feriado, Manutenção..."
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setShowAddException(false)} className="px-4 py-2.5 text-sm font-medium text-gray-600 hover:text-gray-800 transition-colors">
              Cancelar
            </button>
            <button
              onClick={() => void handleAddException()}
              disabled={createException.isPending || !excDate}
              className={[
                'px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors',
                createException.isPending || !excDate
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-gray-900 text-white hover:bg-brand-600',
              ].join(' ')}
            >
              {createException.isPending ? 'Adicionando...' : 'Adicionar'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
