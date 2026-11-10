import type { Appointment, ConsentStatus, ConsentWaiveReason } from '@/types'

export const MOTIVO_DA_DISPENSA: Record<ConsentWaiveReason, string> = {
  SEM_CELULAR: 'Sem celular na mão',
  RECUSOU: 'Recusou assinar no iPad',
  SISTEMA_FORA: 'Sistema fora do ar',
  OUTRO: 'Outro motivo',
}

export type TomDoTermo = 'ok' | 'atencao' | 'pendente' | 'nada'

export interface SituacaoDoTermo {
  label: string
  tom: TomDoTermo
  /** Falta assinar e a sessão ainda vai acontecer: a recepção pode agir. */
  pendente: boolean
}

function dataCurta(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${y.slice(2)}`
}

/**
 * O estado do termo como a agenda o conta. Só EXPÕE o que o servidor mandou:
 * a regra "precisa assinar" vive em `consentimento.precisa_assinar`, e aqui
 * nada é decidido, só lido.
 */
export function situacaoDoTermo(a: Appointment): SituacaoDoTermo {
  if (!a.consent_enabled) return { label: 'Não configurado', tom: 'nada', pendente: false }
  if (a.consent_status === 'SIGNED') return { label: 'Assinado', tom: 'ok', pendente: false }
  if (a.consent_status === 'PAPER') return { label: 'Em papel', tom: 'ok', pendente: false }
  if (a.consent_waived_at) {
    const motivo = a.consent_waived_reason ? MOTIVO_DA_DISPENSA[a.consent_waived_reason] : null
    const quem = a.consent_waived_by ? ` por ${a.consent_waived_by}` : ''
    const porque = motivo ? ` (${motivo.toLowerCase()})` : ''
    return {
      label: `Dispensado${quem} em ${dataCurta(a.consent_waived_at)}${porque}`,
      tom: 'atencao',
      pendente: false,
    }
  }
  if (a.consent_status === 'SIGNING') {
    return { label: 'Assinando no iPad', tom: 'atencao', pendente: true }
  }
  return { label: 'Pendente', tom: 'pendente', pendente: a.status === 'CONFIRMED' }
}

/**
 * Falta o termo (e a ficha) da versão vigente, para a lista de pacientes
 * (PRD 047). `SIGNING` conta como falta, como o DOCS da agenda. Sem versão
 * configurada nada é pendente.
 */
export function semTermo(consentEnabled: boolean, status: ConsentStatus | null | undefined): boolean {
  return consentEnabled && status !== 'SIGNED' && status !== 'PAPER'
}
