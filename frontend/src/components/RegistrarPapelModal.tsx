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
  /** No título, para a recepção ver de quem é o termo que está afirmando. */
  patientName?: string | null
  onClose: () => void
  /** Depois do toast de sucesso; quem abriu decide o que fazer. */
  onRegistrado?: () => void
}

/**
 * "Termo assinado em papel" (PRD 036), numa peça só para a agenda, a pasta do
 * paciente, a linha da lista e o lote (PRD 047). A data é obrigatória e não
 * passa de hoje. A rota exige `agenda.escrever`; sem a permissão o servidor
 * responde 403 e a mensagem dele vai para o toast.
 *
 * O registro vale como assinatura (PRD 036), então "Registrar" só abre com a
 * afirmação marcada e o nome da paciente no título (PRD 063): em 25/11 um
 * clique a mais gravou papel para quem nunca assinou.
 */
export function RegistrarPapelModal({
  open,
  patientId,
  patientName,
  onClose,
  onRegistrado,
}: RegistrarPapelModalProps) {
  const papel = useRegistrarPapel()
  const { showToast } = useToast()
  const [assinadoEm, setAssinadoEm] = useState(hoje)
  const [confirmado, setConfirmado] = useState(false)

  function fechar() {
    setAssinadoEm(hoje())
    setConfirmado(false)
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
    <Modal
      open={open}
      onClose={fechar}
      title={patientName ? `Termo assinado em papel - ${patientName}` : 'Termo assinado em papel'}
      width="sm"
    >
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
        <label className="flex items-start gap-2.5 cursor-pointer rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5">
          <input
            type="checkbox"
            checked={confirmado}
            onChange={(e) => setConfirmado(e.target.checked)}
            className="accent-fuchsia-500 mt-0.5 h-4 w-4 shrink-0"
          />
          <span className="text-sm text-gray-800">
            Confirmo que a paciente assinou o termo impresso e ele está na pasta.
          </span>
        </label>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={fechar}>
            Cancelar
          </Button>
          <Button onClick={confirmar} loading={papel.isPending} disabled={!assinadoEm || !confirmado}>
            Registrar
          </Button>
        </div>
      </div>
    </Modal>
  )
}
