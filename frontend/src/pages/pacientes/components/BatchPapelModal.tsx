import { useMemo, useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useRegistrarPapelEmLote } from '@/hooks/useConsents'
import { formatPhone } from '@/utils/formatPhone'
import { todayStr as hoje } from '@/utils/dateHelpers'
import type { PatientWithStats } from '@/types'

interface BatchPapelModalProps {
  open: boolean
  patients: PatientWithStats[]
  onClose: () => void
  onDone: (registeredCount: number) => void
}

const ROTULO = {
  pending: { texto: '...', cor: 'text-gray-400' },
  registered: { texto: 'Registrado', cor: 'text-emerald-600' },
  already: { texto: 'Já tinha', cor: 'text-gray-500' },
  failed: { texto: 'Erro', cor: 'text-red-500' },
} as const

/**
 * "Assinado em papel" para os selecionados, com UMA data (PRD 047, §7.2 B).
 *
 * Molde do excluir em lote. O aviso da data única fica em destaque: cada papel
 * foi assinado num dia, e aqui todos ganham o mesmo. Quem já tem termo vigente
 * não é alterada - o servidor devolve o que havia e a linha diz "Já tinha".
 */
export function BatchPapelModal({ open, patients, onClose, onDone }: BatchPapelModalProps) {
  const { run, results, isRunning, progress, reset } = useRegistrarPapelEmLote()
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set())
  const [assinadoEm, setAssinadoEm] = useState(hoje)

  const ativos = useMemo(() => patients.filter((p) => !removedIds.has(p.id)), [patients, removedIds])

  const isDone = results.length > 0 && !isRunning
  const registrados = results.filter((r) => r.status === 'registered').length
  const jaTinham = results.filter((r) => r.status === 'already').length
  const falhas = results.filter((r) => r.status === 'failed').length

  const handleClose = () => {
    if (isRunning) return
    reset()
    setRemovedIds(new Set())
    setAssinadoEm(hoje())
    onClose()
    if (isDone) onDone(registrados)
  }

  return (
    <Modal open={open} onClose={handleClose} title="Termo assinado em papel" width="lg">
      <div className="space-y-5">
        {!isDone && (
          <>
            <p className="text-sm text-gray-700">
              Guarde os papéis nas pastas. Aqui fica só o registro, sem PDF.
            </p>
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <strong>A mesma data vale para todas as pessoas selecionadas.</strong> Quem já tem
              termo vigente não é alterada.
            </div>
            <div>
              <label htmlFor="data-do-papel-em-lote" className="text-xs font-medium text-gray-500 block mb-1.5">
                Assinado em
              </label>
              <input
                id="data-do-papel-em-lote"
                type="date"
                value={assinadoEm}
                max={hoje()}
                disabled={isRunning}
                onChange={(e) => setAssinadoEm(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
          </>
        )}

        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1.5">
            Pacientes ({ativos.length})
          </label>
          <div className="rounded-lg border border-gray-200 max-h-64 overflow-y-auto divide-y divide-gray-50">
            {ativos.map((p) => {
              const result = results.find((r) => r.patientId === p.id)
              return (
                <div key={p.id} className="flex items-center justify-between px-3 py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <p className="text-sm text-gray-800 truncate">{p.name ?? 'Sem nome'}</p>
                    <span className="text-xs text-gray-400 flex-shrink-0">{formatPhone(p.phone)}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {result && (
                      <span
                        className={`text-xs font-medium ${ROTULO[result.status].cor}`}
                        title={result.error}
                      >
                        {ROTULO[result.status].texto}
                      </span>
                    )}
                    {!isRunning && !isDone && (
                      <button
                        onClick={() => setRemovedIds((prev) => new Set([...prev, p.id]))}
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

        {isRunning && (
          <div className="rounded-lg bg-brand-50 border border-brand-100 px-4 py-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm font-medium text-brand-700">
                Registrando {progress.done}/{progress.total}...
              </span>
            </div>
            <div className="w-full bg-brand-100 rounded-full h-1.5">
              <div
                className="bg-brand-500 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${(progress.done / progress.total) * 100}%` }}
              />
            </div>
          </div>
        )}

        {isDone && (
          <div className="rounded-lg bg-gray-50 border border-gray-200 px-4 py-3 space-y-1">
            <p className="text-sm font-semibold text-gray-800">Registro concluído</p>
            <p className="text-sm text-emerald-600">
              {registrados} registrado{registrados !== 1 ? 's' : ''}
            </p>
            {jaTinham > 0 && (
              <p className="text-sm text-gray-500">
                {jaTinham} já tinha{jaTinham !== 1 ? 'm' : ''} termo vigente
              </p>
            )}
            {falhas > 0 && (
              <p className="text-sm text-red-500">
                {falhas} erro{falhas !== 1 ? 's' : ''}
              </p>
            )}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={handleClose} disabled={isRunning}>
            {isDone ? 'Fechar' : 'Cancelar'}
          </Button>
          {!isDone && (
            <Button
              onClick={() => void run(ativos.map((p) => p.id), assinadoEm)}
              loading={isRunning}
              disabled={ativos.length === 0 || !assinadoEm}
            >
              Registrar {ativos.length}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  )
}
