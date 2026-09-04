import { api } from './api'
import type { Lead } from '@/types'

interface LeadsResponse {
  status: string
  leads: Lead[]
  total: number
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

  update(leadId: string, payload: Partial<Pick<Lead, 'name' | 'booked'>>) {
    return api
      .put<{ status: string; lead: Lead }>(`/leads/${leadId}`, payload)
      .then((r) => r.data)
  },
}
