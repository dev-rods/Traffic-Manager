import { Modal } from './ui/Modal'
import { Button } from './ui/Button'
import { IconChat } from './ui/icons'
import { formatDateBR, toApiPhone } from '@/utils/format'
import type { SessaoExistente } from '@/types'

interface RemarcacaoDialogProps {
  /** A sessão que o número já tem neste mês; `null` fecha o diálogo. */
  existing: SessaoExistente | null
  /** A data e o horário escolhidos agora. */
  date: string
  time: string
  /** WhatsApp da clínica (só dígitos, com DDI); sem ele o botão some. */
  clinicPhone: string | null
  confirming: boolean
  onConfirm: () => void
  onCancel: () => void
}

/**
 * Uma sessão por mês (PRD 056). O número foi verificado pelo código, então a
 * sessão existente pode ser mostrada. Confirmar cancela essa sessão (o
 * desfecho é interno, PRD 054) e cria a nova no lugar; nunca "manter os dois".
 */
export function RemarcacaoDialog({
  existing,
  date,
  time,
  clinicPhone,
  confirming,
  onConfirm,
  onCancel,
}: RemarcacaoDialogProps) {
  return (
    <Modal open={existing !== null} onClose={onCancel} title="Você já tem uma sessão este mês">
      {existing ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-ink-700">
            Sua sessão de{' '}
            <span className="font-medium text-ink-900">
              {formatDateBR(existing.date)} às {existing.time}
            </span>{' '}
            será substituída por{' '}
            <span className="font-medium text-ink-900">
              {formatDateBR(date)} às {time}
            </span>
            . Confirmar?
          </p>
          <div className="flex flex-col gap-2 text-sm text-ink-500">
            <p>Qualquer dúvida, fale com a clínica.</p>
            {clinicPhone ? (
              <a
                href={`https://wa.me/${toApiPhone(clinicPhone)}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-11 w-fit items-center gap-2 rounded-lg border border-ink-200 px-4 text-sm font-medium text-ink-700 transition-colors hover:border-ink-400"
              >
                <IconChat />
                Falar no WhatsApp
              </a>
            ) : null}
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="ghost" onClick={onCancel} disabled={confirming}>
              Voltar
            </Button>
            <Button onClick={onConfirm} loading={confirming}>
              Confirmar remarcação
            </Button>
          </div>
        </div>
      ) : null}
    </Modal>
  )
}
