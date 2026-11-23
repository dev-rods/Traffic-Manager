import { Modal } from './ui/Modal'
import { Button } from './ui/Button'
import { IconChat } from './ui/icons'
import { formatDateBR, toApiPhone } from '@/utils/format'
import type { SessaoExistente } from '@/types'

interface SessaoFuturaDialogProps {
  /** A sessão futura que o número já tem, em outro mês; `null` fecha o diálogo. */
  existing: SessaoExistente | null
  /** A data e o horário escolhidos agora. */
  date: string
  time: string
  /** WhatsApp da clínica (só dígitos, com DDI); sem ele o botão some. */
  clinicPhone: string | null
  confirming: boolean
  onRemarcar: () => void
  onMaisUma: () => void
  onCancel: () => void
}

/**
 * Sessão futura em outro mês (PRD 060). Não é bloqueio, é pergunta: em
 * 23/11/2026 duas pacientes que queriam remarcar criaram a sessão nova em
 * dezembro e a de novembro ficou de pé até a recepção cancelar à mão. Mês
 * diferente passava em silêncio (PRD 056); agora a pessoa escolhe entre
 * remarcar a sessão que já tem ou ficar com as duas.
 */
export function SessaoFuturaDialog({
  existing,
  date,
  time,
  clinicPhone,
  confirming,
  onRemarcar,
  onMaisUma,
  onCancel,
}: SessaoFuturaDialogProps) {
  return (
    <Modal open={existing !== null} onClose={onCancel} title="Você já tem uma sessão marcada">
      {existing ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-ink-700">
            Você já tem uma sessão em{' '}
            <span className="font-medium text-ink-900">
              {formatDateBR(existing.date)} às {existing.time}
            </span>
            . O que você quer fazer?
          </p>
          {existing.areas ? <p className="text-xs text-ink-500">Áreas: {existing.areas}</p> : null}
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
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
            <Button variant="ghost" onClick={onCancel} disabled={confirming}>
              Voltar
            </Button>
            <Button variant="muted" onClick={onMaisUma} disabled={confirming}>
              Marcar mais uma
            </Button>
            <Button onClick={onRemarcar} loading={confirming}>
              Remarcar essa sessão para {formatDateBR(date)}
              {time ? ` às ${time}` : ''}
            </Button>
          </div>
        </div>
      ) : null}
    </Modal>
  )
}
