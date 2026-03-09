import { useState } from 'react'
import { usePatients } from '@/hooks/usePatients'
import { useDebounce } from '@/hooks/useDebounce'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { PatientSearch } from './components/PatientSearch'
import { PatientsTable } from './components/PatientsTable'
import { CreatePatientModal } from './components/CreatePatientModal'
import { EditPatientModal } from './components/EditPatientModal'
import type { PatientWithStats } from '@/types'

export function PacientesPage() {
  const [search, setSearch] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [editingPatient, setEditingPatient] = useState<PatientWithStats | null>(null)
  const debouncedSearch = useDebounce(search)

  const { data, isLoading, isError, error, refetch } = usePatients({
    search: debouncedSearch || undefined,
    per_page: 50,
  })

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Pacientes</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            {data ? `${data.total} paciente${data.total !== 1 ? 's' : ''}` : 'Carregando...'}
          </p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-600"
        >
          + Cadastrar paciente
        </button>
      </div>

      <PatientSearch value={search} onChange={setSearch} />

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
              <button
                onClick={() => setCreateOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-4 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-brand-600"
              >
                + Cadastrar paciente
              </button>
            ) : undefined
          }
        />
      ) : (
        <PatientsTable patients={data.items} onSelect={setEditingPatient} />
      )}

      <CreatePatientModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <EditPatientModal patient={editingPatient} onClose={() => setEditingPatient(null)} />
    </div>
  )
}
