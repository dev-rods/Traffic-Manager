import { useState, useMemo, useCallback } from 'react'
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
  const [batchOpen, setBatchOpen] = useState(false)
  const [batchPatients, setBatchPatients] = useState<PatientWithStats[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const debouncedSearch = useDebounce(search)

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
              💬 Enviar WhatsApp
            </Button>
          </div>
        </div>
      )}

      <CreatePatientModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <EditPatientModal patient={editingPatient} onClose={() => setEditingPatient(null)} />
      <BatchMessageModal
        open={batchOpen}
        patients={batchPatients}
        availableDates={availableDates}
        clinicTemplate={clinic?.batch_message_template}
        onClose={() => setBatchOpen(false)}
        onDone={() => { setSelectedIds(new Set()); setBatchPatients([]) }}
      />
    </div>
  )
}
