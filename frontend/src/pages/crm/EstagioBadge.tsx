import { Badge } from '@/components/ui/Badge'
import type { Lead } from '@/types'
import { ESTAGIOS, ESTAGIOS_DA_AGENDA, FONTE_LABEL } from './estagios'

interface EstagioBadgeProps {
  lead: Lead
  /** Abre a correcao. Omitido (ou fato da agenda), o badge e so leitura. */
  onCorrigir?: () => void
}

const ICONE_DA_FONTE: Record<string, string> = {
  MODELO: '◆',
  MANUAL: '✎',
  HISTORICO: '◷',
}

/** Badge do estagio com o motivo e a fonte. Clicavel quando ha `onCorrigir`. */
export function EstagioBadge({ lead, onCorrigir }: EstagioBadgeProps) {
  if (!lead.stage) {
    return <Badge variant="neutral">Aguardando o processamento</Badge>
  }
  const info = ESTAGIOS[lead.stage]
  const fonte = lead.stage_source ? FONTE_LABEL[lead.stage_source] : ''
  const icone = lead.stage_source ? ICONE_DA_FONTE[lead.stage_source] : undefined
  const editavel = Boolean(onCorrigir) && !ESTAGIOS_DA_AGENDA.includes(lead.stage)

  const conteudo = (
    <span className="inline-flex items-center gap-1.5">
      <Badge variant={info.variant}>{info.label}</Badge>
      {icone && (
        <span aria-label={fonte} title={fonte} className="text-xs text-gray-400">
          {icone}
        </span>
      )}
    </span>
  )

  return (
    <div className="flex flex-col gap-0.5">
      {editavel ? (
        <button
          type="button"
          onClick={onCorrigir}
          aria-label={`Corrigir estágio de ${lead.name ?? lead.phone}`}
          title="Corrigir estágio"
          className="text-left cursor-pointer rounded-md transition-colors duration-150 hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
        >
          {conteudo}
        </button>
      ) : (
        conteudo
      )}
      {lead.stage_reason && <span className="text-xs text-gray-500">{lead.stage_reason}</span>}
    </div>
  )
}
