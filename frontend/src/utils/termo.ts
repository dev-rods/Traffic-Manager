import type { Appointment, ConsentStatus, ConsentWaiveReason } from '@/types'
import { formatShortDateBR } from '@/utils/formatDate'

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
  /** Nenhum termo foi sequer iniciado (nem pelo link, nem no iPad). */
  semNada: boolean
}

// Timestamp → dia em São Paulo. Cortar o ISO daria o dia de UTC.
const dataCurta = formatShortDateBR

/**
 * O estado do termo como a agenda o conta. Só EXPÕE o que o servidor mandou:
 * a regra "precisa assinar" vive em `consentimento.precisa_assinar`, e aqui
 * nada é decidido, só lido.
 *
 * Rótulos (PRD 065): concluído é particípio; pendente começa com "Falta" e
 * diz o que falta. "Assinando" saiu em 26/11/2026: a Essência não distinguia
 * de "Assinado". A aba histórica da pasta (`TermoDeConsentimento`) repete
 * estes textos por linha; mudar aqui é mudar lá.
 */
export function situacaoDoTermo(a: Appointment): SituacaoDoTermo {
  if (!a.consent_enabled) return { label: 'Não configurado', tom: 'nada', pendente: false, semNada: false }
  if (a.consent_status === 'SIGNED') return { label: 'Assinado', tom: 'ok', pendente: false, semNada: false }
  if (a.consent_status === 'PAPER') {
    return { label: 'Assinado em papel', tom: 'ok', pendente: false, semNada: false }
  }
  if (a.consent_waived_at) {
    const motivo = a.consent_waived_reason ? MOTIVO_DA_DISPENSA[a.consent_waived_reason] : null
    const quem = a.consent_waived_by ? ` por ${a.consent_waived_by}` : ''
    const porque = motivo ? ` (${motivo.toLowerCase()})` : ''
    return {
      label: `Dispensado${quem} em ${dataCurta(a.consent_waived_at)}${porque}`,
      tom: 'atencao',
      pendente: false,
      semNada: false,
    }
  }
  // Pelo link do celular (PRD 048) ou no iPad: ainda falta terminar. O front
  // não sabe a origem; "(abriu o link)" é o caso que dura (no iPad, SIGNING
  // vive segundos).
  if (a.consent_status === 'SIGNING') {
    return { label: 'Falta assinar (abriu o link)', tom: 'pendente', pendente: true, semNada: false }
  }
  if (a.consent_status === 'FILLING') {
    return { label: 'Falta a ficha (abriu o link)', tom: 'pendente', pendente: true, semNada: false }
  }
  return { label: 'Falta o termo', tom: 'pendente', pendente: a.status === 'CONFIRMED', semNada: true }
}

/**
 * Falta o termo (e a ficha) da versão vigente, para a lista de pacientes
 * (PRD 047). `SIGNING` conta como falta, como o DOCS da agenda. Sem versão
 * configurada nada é pendente.
 */
export function semTermo(consentEnabled: boolean, status: ConsentStatus | null | undefined): boolean {
  return consentEnabled && status !== 'SIGNED' && status !== 'PAPER'
}
