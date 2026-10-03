import { api } from './api'
import type { Lead } from '@/types'

/** Totais do conjunto inteiro, contados no banco - não da página carregada. */
export interface LeadTotals {
  total: number
  convertidos: number
  nao_convertidos: number
}

/**
 * O que o Google Ads já recebeu desta clínica.
 *
 * Relata fato, não previsão: `aguardando` conta conversões registradas e ainda
 * não enviadas, sem tentar antecipar quais o uploader vai considerar elegíveis
 * (essa regra vive no uploader, e só lá).
 */
export interface ConversionsSummary {
  aguardando: number
  aguardando_cents: number
  enviadas: number
  enviadas_cents: number
  retratadas: number
  canceladas: number
  /** ISO, ou null quando nada subiu ainda. */
  ultimo_envio: string | null
}

interface LeadsResponse {
  status: string
  leads: Lead[]
  /** Conjunto inteiro. Já foi `len(leads)`, e a tela mostrava o tamanho da página. */
  total: number
  totals: LeadTotals
  /** null quando o resumo falhou: a listagem continua, os contadores somem. */
  conversions: ConversionsSummary | null
}

export interface LeadListParams {
  startDate?: string
  endDate?: string
  booked?: boolean
  /** Origens a excluir, separadas por virgula. Ex: 'whatsapp'. */
  excludeSource?: string
  limit?: number
  offset?: number
}

export const leadsService = {
  list(clinicId: string, params?: LeadListParams) {
    return api
      .get<LeadsResponse>(`/clinics/${clinicId}/leads`, { params })
      .then((r) => r.data)
  },

  /** Manda o bot abrir conversa. O servidor revalida a elegibilidade. */
  iniciarPeloBot(leadId: string) {
    return api
      .post<{ status: string; leadId: string }>(`/leads/${leadId}/iniciar-pelo-bot`)
      .then((r) => r.data)
  },

  /** Alterna "Ja iniciada": marca, ou desmarca se foi uma pessoa que marcou. */
  alternarContatoManual(leadId: string) {
    return api
      .post<{ status: string; first_contact_channel: string | null }>(
        `/leads/${leadId}/marcar-contatado`
      )
      .then((r) => r.data)
  },

  update(leadId: string, payload: Partial<Pick<Lead, 'name' | 'booked'>>) {
    return api
      .put<{ status: string; lead: Lead }>(`/leads/${leadId}`, payload)
      .then((r) => r.data)
  },
}
