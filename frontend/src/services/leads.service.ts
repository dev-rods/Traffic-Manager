import { api } from './api'
import type { Lead } from '@/types'

interface LeadsResponse {
  status: string
  leads: Lead[]
  total: number
}

export const leadsService = {
  list(clinicId: string, params?: { startDate?: string; endDate?: string; booked?: boolean; limit?: number; offset?: number }) {
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
