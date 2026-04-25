import { useMemo, useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useBatchDeletePatients } from '@/hooks/usePatients'
import { formatPhone } from '@/utils/formatPhone'
import type { PatientWithStats } from '@/types'

interface BatchDeletePatientsModalProps {
  open: boolean
  patients: PatientWithStats[]
  onClose: () => void
  onDone: (deletedCount: number) => void
}

export function BatchDeletePatientsModal({ open, patients, onClose, onDone }: BatchDeletePatientsModalProps) {
  const { run, results, isDeleting, progress, reset } = useBatchDeletePatients()
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set())

  const activePatients = useMemo(
    () => patients.filter((p) => !removedIds.has(p.id)),
    [patients, removedIds],
  )

  const isDone = results.length > 0 && !isDeleting
  const deletedCount = results.filter((r) => r.status === 'deleted').length
  const failedCount = results.filter((r) => r.status === 'failed').length

  const handleRemove = (id: string) => {
    setRemovedIds((prev) => new Set([...prev, id]))
  }

  const handleConfirm = async () => {
    await run(activePatients.map((p) => p.id))
  }

  const handleClose = () => {
    if (isDeleting) return
    reset()
    setRemovedIds(new Set())
    onClose()
    if (isDone) onDone(deletedCount)
  }

  return (
    <Modal open={open} onClose={handleClose} title="Excluir pacientes" width="lg">
      <div className="space-y-5">
        {!isDone && (
          <p className="text-sm text-gray-700">
            Você está prestes a excluir{' '}
            <strong className="text-gray-900">
              {activePatients.length} paciente{activePatients.length !== 1 ? 's' : ''}
            </strong>
            . O histórico de agendamentos é preservado e o paciente é restaurado automaticamente
            se voltar a entrar em contato.
          </p>
        )}

        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1.5">
            Pacientes ({activePatients.length})
          </label>
          <div className="rounded-lg border border-gray-200 max-h-64 overflow-y-auto divide-y divide-gray-50">
            {activePatients.map((p) => {
              const result = results.find((r) => r.patientId === p.id)
              return (
                <div key={p.id} className="flex items-center justify-between px-3 py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <p className="text-sm text-gray-800 truncate">{p.name ?? 'Sem nome'}</p>
                    <span className="text-xs text-gray-400 flex-shrink-0">{formatPhone(p.phone)}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {result && (
                      <span className={[
                        'text-xs font-medium',
                        result.status === 'deleted'
                          ? 'text-emerald-600'
                          : result.status === 'failed'
                            ? 'text-red-500'
                            : 'text-gray-400',
                      ].join(' ')}>
                        {result.status === 'deleted'
                          ? 'Excluído'
                          : result.status === 'failed'
                            ? 'Falhou'
                            : '...'}
                      </span>
                    )}
                    {!isDeleting && !isDone && (
                      <button
                        onClick={() => handleRemove(p.id)}
                        className="text-xs text-gray-400 hover:text-red-500 transition-colors cursor-pointer"
                        aria-label={`Remover ${p.name ?? 'paciente'} da seleção`}
                      >
                        &times;
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {isDeleting && (
          <div className="rounded-lg bg-red-50 border border-red-100 px-4 py-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-4 h-4 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm font-medium text-red-700">
                Excluindo {progress.done}/{progress.total}...
              </span>
            </div>
            <div className="w-full bg-red-100 rounded-full h-1.5">
              <div
                className="bg-red-500 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${(progress.done / progress.total) * 100}%` }}
              />
            </div>
          </div>
        )}

        {isDone && (
          <div className="rounded-lg bg-gray-50 border border-gray-200 px-4 py-3 space-y-1">
            <p className="text-sm font-semibold text-gray-800">Exclusão concluída</p>
            <p className="text-sm text-emerald-600">
              {deletedCount} paciente{deletedCount !== 1 ? 's' : ''} excluído{deletedCount !== 1 ? 's' : ''}
            </p>
            {failedCount > 0 && (
              <p className="text-sm text-red-500">
                {failedCount} falha{failedCount !== 1 ? 's' : ''}
              </p>
            )}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={handleClose} disabled={isDeleting}>
            {isDone ? 'Fechar' : 'Cancelar'}
          </Button>
          {!isDone && (
            <Button
              variant="danger"
              onClick={() => void handleConfirm()}
              loading={isDeleting}
              disabled={activePatients.length === 0}
            >
              Excluir {activePatients.length} paciente{activePatients.length !== 1 ? 's' : ''}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  )
}
