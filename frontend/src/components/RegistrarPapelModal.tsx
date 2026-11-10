import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useToast } from '@/components/ui/toastContext'
import { useRegistrarPapel } from '@/hooks/useConsents'
import { todayStr as hoje } from '@/utils/dateHelpers'

function mensagemDe(erro: unknown): string | undefined {
  return (erro as { response?: { data?: { message?: string } } })?.response?.data?.message
}

interface RegistrarPapelModalProps {
  open: boolean
  patientId: string
  onClose: () => void
  /** Depois do toast de sucesso; quem abriu decide o que fazer. */
  onRegistrado?: () => void
}

/**
 * "Termo assinado em papel" (PRD 036), numa peça só para a agenda, a pasta do
 * paciente, a linha da lista e o lote (PRD 047). A data é obrigatória e não
 * passa de hoje. A rota exige `agenda.escrever`; sem a permissão o servidor
 * responde 403 e a mensagem dele vai para o toast.
 */
export function RegistrarPapelModal({ open, patientId, onClose, onRegistrado }: RegistrarPapelModalProps) {
  const papel = useRegistrarPapel()
  const { showToast } = useToast()
  const [assinadoEm, setAssinadoEm] = useState(hoje)

  function fechar() {
    setAssinadoEm(hoje())
    onClose()
  }

  function confirmar() {
    papel.mutate(
      { patientId, signedAt: assinadoEm },
      {
        onSuccess: () => {
          fechar()
          showToast({ message: 'Termo em papel registrado' })
          onRegistrado?.()
        },
        onError: (erro) =>
          showToast({
            message: mensagemDe(erro) ?? 'Não foi possível registrar o termo.',
            variant: 'error',
          }),
      }
    )
  }

  return (
    <Modal open={open} onClose={fechar} title="Termo assinado em papel" width="sm">
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          Guarde o papel na pasta da paciente. Aqui fica só o registro, sem PDF.
        </p>
        <div>
          <label htmlFor="data-do-papel" className="text-xs font-medium text-gray-500 block mb-1.5">
            Assinado em
          </label>
          <input
            id="data-do-papel"
            type="date"
            value={assinadoEm}
            max={hoje()}
            onChange={(e) => setAssinadoEm(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={fechar}>
            Cancelar
          </Button>
          <Button onClick={confirmar} loading={papel.isPending} disabled={!assinadoEm}>
            Registrar
          </Button>
        </div>
      </div>
    </Modal>
  )
}
