import { useState, useMemo, useCallback, useEffect } from 'react'
import { usePatients } from '@/hooks/usePatients'
import { useClinic } from '@/hooks/useClinic'
import { useAvailabilityRules } from '@/hooks/useAvailabilityRules'
import { useActiveConversations, usePauseBot, useResumeBot } from '@/hooks/useBot'
import { useDebounce } from '@/hooks/useDebounce'
import { todayStr } from '@/utils/dateHelpers'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { Button } from '@/components/ui/Button'
import { Pagination } from '@/components/ui/Pagination'
import { PatientSearch } from './components/PatientSearch'
import { PatientsTable } from './components/PatientsTable'
import { CreatePatientModal } from './components/CreatePatientModal'
import { EditPatientModal } from './components/EditPatientModal'
import { BatchMessageModal } from './components/BatchMessageModal'
import { DeletePatientConfirmModal } from './components/DeletePatientConfirmModal'
import { BatchDeletePatientsModal } from './components/BatchDeletePatientsModal'
import { WhatsAppIcon, TrashIcon } from '@/components/ui/Icons'
import type { PatientWithStats } from '@/types'

type NextVisitFilter = 'all' | 'with' | 'without'
type LastMessageFilter = 'all' | '7' | '15' | '30' | '60' | 'never'

export function PacientesPage() {
  const [search, setSearch] = useState('')
  const [nextVisitFilter, setNextVisitFilter] = useState<NextVisitFilter>('all')
  const [lastMessageFilter, setLastMessageFilter] = useState<LastMessageFilter>('all')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  const [createOpen, setCreateOpen] = useState(false)
  const [editingPatient, setEditingPatient] = useState<PatientWithStats | null>(null)
  const [deletingPatient, setDeletingPatient] = useState<PatientWithStats | null>(null)
  const [batchOpen, setBatchOpen] = useState(false)
  const [batchPatients, setBatchPatients] = useState<PatientWithStats[]>([])
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false)
  const [batchDeleteTargets, setBatchDeleteTargets] = useState<PatientWithStats[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'info'; message: string } | null>(null)
  const debouncedSearch = useDebounce(search)

  useEffect(() => {
    if (!feedback) return
    const timer = window.setTimeout(() => setFeedback(null), 4000)
    return () => window.clearTimeout(timer)
  }, [feedback])

  // Bot pause per patient
  const { data: activeData } = useActiveConversations()
  const pauseBot = usePauseBot()
  const resumeBot = useResumeBot()
  const pausedPhones = useMemo(() => {
    const set = new Set<string>()
    for (const c of activeData?.conversations ?? []) {
      if (c.bot_paused) set.add(c.phone)
    }
    return set
  }, [activeData])

  const handleTogglePause = useCallback((phone: string) => {
    const clean = phone.replace(/\D/g, '')
    if (pausedPhones.has(clean)) {
      resumeBot.mutate(clean)
    } else {
      pauseBot.mutate(clean)
    }
  }, [pausedPhones, pauseBot, resumeBot])

  // Fetch available dates for WhatsApp message, limited by max_future_dates
  const { data: clinic } = useClinic()
  const { data: rulesData } = useAvailabilityRules()
  const availableDates = useMemo(() => {
    const today = todayStr()
    const maxDates = clinic?.max_future_dates ?? 5
    return (rulesData?.data ?? [])
      .filter((r) => r.rule_date !== null && r.rule_date! >= today)
      .map((r) => r.rule_date as string)
      .sort()
      .slice(0, maxDates)
  }, [rulesData, clinic])

  const { data, isLoading, isError, error, refetch } = usePatients({
    search: debouncedSearch || undefined,
    next_visit: nextVisitFilter !== 'all' ? nextVisitFilter : undefined,
    last_message_days: lastMessageFilter !== 'all' ? lastMessageFilter : undefined,
    page,
    per_page: perPage,
  })

  // Reset page when filters change
  const handleSearch = useCallback((v: string) => { setSearch(v); setPage(1) }, [])
  const handleNextVisitFilter = useCallback((v: NextVisitFilter) => { setNextVisitFilter(v); setPage(1) }, [])
  const handleLastMessageFilter = useCallback((v: LastMessageFilter) => { setLastMessageFilter(v); setPage(1) }, [])

  const patients = useMemo(() => data?.items ?? [], [data])

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const handleToggleAll = useCallback(() => {
    setSelectedIds((prev) => {
      if (patients.length > 0 && patients.every((p) => prev.has(p.id))) {
        return new Set()
      }
      return new Set(patients.map((p) => p.id))
    })
  }, [patients])

  const selectedPatients = useMemo(
    () => patients.filter((p) => selectedIds.has(p.id)),
    [patients, selectedIds],
  )

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Pacientes</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {data ? `${data.total} paciente${data.total !== 1 ? 's' : ''}` : 'Carregando...'}
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>+ Cadastrar paciente</Button>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex-1">
          <PatientSearch value={search} onChange={handleSearch} />
        </div>
        <select
          value={nextVisitFilter}
          onChange={(e) => handleNextVisitFilter(e.target.value as NextVisitFilter)}
          className="border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer"
        >
          <option value="all">Todas as visitas</option>
          <option value="with">Com próxima visita</option>
          <option value="without">Sem próxima visita</option>
        </select>
        <select
          value={lastMessageFilter}
          onChange={(e) => handleLastMessageFilter(e.target.value as LastMessageFilter)}
          className="border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer"
        >
          <option value="all">Última mensagem</option>
          <option value="7">Últimos 7 dias</option>
          <option value="15">Últimos 15 dias</option>
          <option value="30">Últimos 30 dias</option>
          <option value="60">Últimos 60 dias</option>
          <option value="never">Nunca contatado</option>
        </select>
      </div>

      {isLoading ? (
        <SkeletonTable rows={8} />
      ) : isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar pacientes.'}
          onRetry={() => refetch()}
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title={search ? 'Nenhum paciente encontrado' : 'Nenhum paciente cadastrado'}
          description={
            search
              ? 'Tente buscar com outro termo.'
              : 'Cadastre o primeiro paciente para comecar.'
          }
          action={
            !search ? (
              <Button size="sm" onClick={() => setCreateOpen(true)}>+ Cadastrar paciente</Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <PatientsTable
            patients={data.items}
            onSelect={setEditingPatient}
            onWhatsApp={(p) => { setBatchPatients([p]); setBatchOpen(true) }}
            onPauseBot={handleTogglePause}
            onDelete={setDeletingPatient}
            pausedPhones={pausedPhones}
            pauseLoading={pauseBot.isPending || resumeBot.isPending}
            selectedIds={selectedIds}
            onToggleSelect={handleToggleSelect}
            onToggleAll={handleToggleAll}
          />
          <Pagination
            page={page}
            perPage={perPage}
            total={data.total}
            onPageChange={setPage}
            onPerPageChange={setPerPage}
          />
        </>
      )}

      {/* Batch action bar */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-0 left-56 right-0 bg-white border-t border-gray-200 shadow-lg px-6 py-3 flex items-center justify-between z-40">
          <p className="text-sm text-gray-700 font-medium">
            {selectedIds.size} paciente{selectedIds.size !== 1 ? 's' : ''} selecionado{selectedIds.size !== 1 ? 's' : ''}
          </p>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => setSelectedIds(new Set())}>
              Limpar seleção
            </Button>
            <Button variant="success" size="sm" onClick={() => { setBatchPatients(selectedPatients); setBatchOpen(true) }}>
              <WhatsAppIcon className="w-4 h-4" />
              Enviar WhatsApp
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => { setBatchDeleteTargets(selectedPatients); setBatchDeleteOpen(true) }}
            >
              <TrashIcon className="w-4 h-4" />
              Excluir selecionados
            </Button>
          </div>
        </div>
      )}

      <CreatePatientModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSuccess={(status, name) =>
          setFeedback({
            tone: status === 'RESTORED' ? 'info' : 'success',
            message:
              status === 'RESTORED'
                ? `${name} foi restaurado e voltou para a lista.`
                : `${name} foi cadastrado.`,
          })
        }
      />
      <EditPatientModal patient={editingPatient} onClose={() => setEditingPatient(null)} />
      <DeletePatientConfirmModal
        patient={deletingPatient}
        onClose={() => setDeletingPatient(null)}
        onSuccess={(name) =>
          setFeedback({ tone: 'success', message: `${name} foi excluído.` })
        }
      />
      <BatchMessageModal
        open={batchOpen}
        patients={batchPatients}
        availableDates={availableDates}
        clinicTemplate={clinic?.batch_message_template}
        onClose={() => setBatchOpen(false)}
        onDone={() => { setSelectedIds(new Set()); setBatchPatients([]) }}
      />
      <BatchDeletePatientsModal
        open={batchDeleteOpen}
        patients={batchDeleteTargets}
        onClose={() => setBatchDeleteOpen(false)}
        onDone={(deletedCount) => {
          setSelectedIds(new Set())
          setBatchDeleteTargets([])
          if (deletedCount > 0) {
            setFeedback({
              tone: 'success',
              message: `${deletedCount} paciente${deletedCount !== 1 ? 's' : ''} excluído${deletedCount !== 1 ? 's' : ''}.`,
            })
          }
        }}
      />

      {feedback && (
        <div
          className={[
            'fixed bottom-6 right-6 z-50 max-w-sm rounded-lg px-4 py-3 shadow-lg text-sm font-medium border',
            feedback.tone === 'info'
              ? 'bg-amber-50 border-amber-200 text-amber-800'
              : 'bg-emerald-50 border-emerald-200 text-emerald-800',
          ].join(' ')}
          role="status"
        >
          {feedback.message}
        </div>
      )}
    </div>
  )
}
