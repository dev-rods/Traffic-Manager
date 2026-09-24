import { useState, useMemo, useCallback, useEffect } from 'react'
import { usePatients } from '@/hooks/usePatients'
import { useClinic } from '@/hooks/useClinic'
import { useAvailabilityRules } from '@/hooks/useAvailabilityRules'
import { useActiveConversations, usePauseBot, useResumeBot } from '@/hooks/useBot'
import { useDebounce } from '@/hooks/useDebounce'
import { useSelection } from '@/hooks/useSelection'
import { todayStr } from '@/utils/dateHelpers'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { Button } from '@/components/ui/Button'
import { Pagination } from '@/components/ui/Pagination'
import { PatientSearch } from './components/PatientSearch'
import { Drawer } from '@/components/ui/Drawer'
import { FiltrosDePacientes } from './components/FiltrosDePacientes'
import { contaFiltrosAtivos } from './components/contagemDeFiltros'
import type { NextVisitFilter, LastMessageFilter } from './components/contagemDeFiltros'
import { PatientsTable } from './components/PatientsTable'
import { CreatePatientModal } from './components/CreatePatientModal'
import { EditPatientModal } from './components/EditPatientModal'
import { BatchMessageModal } from './components/BatchMessageModal'
import { DeletePatientConfirmModal } from './components/DeletePatientConfirmModal'
import { BatchDeletePatientsModal } from './components/BatchDeletePatientsModal'
import { AcoesEmLote } from './components/AcoesEmLote'
import type { PatientWithStats } from '@/types'

export function PacientesPage() {
  const [search, setSearch] = useState('')
  const [nextVisitFilter, setNextVisitFilter] = useState<NextVisitFilter>('all')
  const [lastMessageFilter, setLastMessageFilter] = useState<LastMessageFilter>('all')
  const [lastVisitBefore, setLastVisitBefore] = useState('')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  const [createOpen, setCreateOpen] = useState(false)
  const [editingPatient, setEditingPatient] = useState<PatientWithStats | null>(null)
  const [deletingPatient, setDeletingPatient] = useState<PatientWithStats | null>(null)
  const [batchOpen, setBatchOpen] = useState(false)
  const [batchPatients, setBatchPatients] = useState<PatientWithStats[]>([])
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false)
  const [batchDeleteTargets, setBatchDeleteTargets] = useState<PatientWithStats[]>([])
  const [filtrosAbertos, setFiltrosAbertos] = useState(false)
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
    last_visit_before: lastVisitBefore || undefined,
    page,
    per_page: perPage,
  })

  const patients = useMemo(() => data?.items ?? [], [data])

  const {
    selectedIds,
    selectedItems: selectedPatients,
    pageFullySelected,
    toggle: handleToggleSelect,
    togglePage: handleToggleAll,
    clear: clearSelection,
  } = useSelection(patients)

  // Reset page when filters change, and drop the selection — it spans pages, so keeping it
  // would carry patients that no longer match the filter into the next batch action
  const handleSearch = useCallback((v: string) => { setSearch(v); setPage(1); clearSelection() }, [clearSelection])
  const handleNextVisitFilter = useCallback((v: NextVisitFilter) => { setNextVisitFilter(v); setPage(1); clearSelection() }, [clearSelection])
  const handleLastMessageFilter = useCallback((v: LastMessageFilter) => { setLastMessageFilter(v); setPage(1); clearSelection() }, [clearSelection])
  const handleLastVisitBefore = useCallback((v: string) => { setLastVisitBefore(v); setPage(1); clearSelection() }, [clearSelection])

  const filtrosAtivos = contaFiltrosAtivos({
    nextVisit: nextVisitFilter,
    lastMessage: lastMessageFilter,
    lastVisitBefore,
  })

  return (
    <div
      className={[
        'p-4 md:p-8 space-y-4 md:space-y-6',
        // A regua de acoes e `fixed` e cobriria a paginacao e as ultimas
        // linhas. A folga so aparece quando ha selecao, para nao deixar um
        // vazio permanente no fim da pagina.
        selectedIds.size > 0 ? 'pb-32 md:pb-24' : '',
      ].join(' ')}
    >
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Pacientes</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {data ? `${data.total} paciente${data.total !== 1 ? 's' : ''}` : 'Carregando...'}
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>+ Cadastrar paciente</Button>
      </div>

      {/* A busca fica sempre a vista; os tres filtros so cabem em linha de
          `md` para cima. Em celular eles vao para um drawer, e o botao carrega
          quantos estao ligados - senao a pessoa nao tem como saber que a lista
          esta filtrada sem abrir. */}
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <PatientSearch value={search} onChange={handleSearch} />
        </div>

        <button
          type="button"
          onClick={() => setFiltrosAbertos(true)}
          className="md:hidden flex h-11 items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 cursor-pointer"
        >
          Filtros
          {filtrosAtivos > 0 && (
            <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-500 px-1 text-[11px] font-semibold text-white">
              {filtrosAtivos}
            </span>
          )}
        </button>

        <div className="hidden md:block">
          <FiltrosDePacientes
            nextVisit={nextVisitFilter}
            lastMessage={lastMessageFilter}
            lastVisitBefore={lastVisitBefore}
            onNextVisit={handleNextVisitFilter}
            onLastMessage={handleLastMessageFilter}
            onLastVisitBefore={handleLastVisitBefore}
          />
        </div>
      </div>

      <Drawer
        open={filtrosAbertos}
        onClose={() => setFiltrosAbertos(false)}
        title="Filtros"
        side="right"
      >
        <FiltrosDePacientes
          empilhado
          nextVisit={nextVisitFilter}
          lastMessage={lastMessageFilter}
          lastVisitBefore={lastVisitBefore}
          onNextVisit={handleNextVisitFilter}
          onLastMessage={handleLastMessageFilter}
          onLastVisitBefore={handleLastVisitBefore}
        />
      </Drawer>

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
            allSelected={pageFullySelected}
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

      <AcoesEmLote
        quantidade={selectedIds.size}
        onLimpar={clearSelection}
        onWhatsApp={() => { setBatchPatients(selectedPatients); setBatchOpen(true) }}
        onExcluir={() => { setBatchDeleteTargets(selectedPatients); setBatchDeleteOpen(true) }}
      />

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
        onDone={() => { clearSelection(); setBatchPatients([]) }}
      />
      <BatchDeletePatientsModal
        open={batchDeleteOpen}
        patients={batchDeleteTargets}
        onClose={() => setBatchDeleteOpen(false)}
        onDone={(deletedCount) => {
          clearSelection()
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
