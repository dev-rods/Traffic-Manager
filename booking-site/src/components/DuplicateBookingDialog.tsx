import { Modal } from './ui/Modal'
import { Button } from './ui/Button'

interface DuplicateBookingDialogProps {
  // Agendamentos futuros que o número já tem; `null` fecha o diálogo.
  existingCount: number | null
  confirming: boolean
  onConfirm: () => void
  onCancel: () => void
}

/**
 * Lembra quem já tem agendamento futuro antes de criar outro. Não bloqueia:
 * duas pessoas podem agendar pelo mesmo telefone. Não diz quando nem o quê,
 * porque criar não exige código e o número pode ser de outra pessoa; quem
 * quiser conferir usa "Meus agendamentos".
 */
export function DuplicateBookingDialog({ existingCount, confirming, onConfirm, onCancel }: DuplicateBookingDialogProps) {
  const many = (existingCount ?? 0) > 1

  return (
    <Modal open={existingCount !== null} onClose={onCancel} title="Você já tem agendamento">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-700">
          Este número já tem {many ? `${existingCount} agendamentos futuros` : 'um agendamento futuro'} nesta
          clínica. Quer manter {many ? 'todos e marcar este também' : 'os dois'}?
        </p>
        <p className="text-sm text-ink-500">
          Para conferir datas e horários, use “Meus agendamentos” no topo da página.
        </p>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="ghost" onClick={onCancel} disabled={confirming}>
            Voltar
          </Button>
          <Button onClick={onConfirm} loading={confirming}>
            {many ? 'Manter todos' : 'Manter os dois'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
