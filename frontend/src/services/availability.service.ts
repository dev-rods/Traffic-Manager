import { api } from './api'
import type { AvailabilityRule } from '@/types'

interface ListAvailabilityRulesResponse {
  status: string
  data: AvailabilityRule[]
}

interface AvailableSlotsResponse {
  status: string
  clinicId: string
  date: string
  serviceId: string
  slots: string[]
  totalSlots: number
}

export const availabilityService = {
  listRules(clinicId: string) {
    return api
      .get<ListAvailabilityRulesResponse>(`/clinics/${clinicId}/availability-rules`)
      .then((r) => r.data)
  },

  getSlots(clinicId: string, date: string, serviceId: string, totalDuration?: number) {
    return api
      .get<AvailableSlotsResponse>(`/clinics/${clinicId}/available-slots`, {
        params: { date, serviceId, ...(totalDuration ? { totalDuration } : {}) },
      })
      .then((r) => r.data)
  },
}
