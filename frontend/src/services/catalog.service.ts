import { api } from './api'
import type { Service, Area, DiscountRule } from '@/types'

export const catalogService = {
  listServices(clinicId: string) {
    return api
      .get<Service[]>(`/clinics/${clinicId}/services`)
      .then((r) => r.data)
  },

  getServiceWithAreas(clinicId: string, serviceId: string) {
    return api
      .get<Service>(`/clinics/${clinicId}/services/${serviceId}?include=areas`)
      .then((r) => r.data)
  },

  listAreas(clinicId: string, serviceId: string) {
    return api
      .get<Area[]>(`/clinics/${clinicId}/services/${serviceId}/areas`)
      .then((r) => r.data)
  },

  getDiscountRules(clinicId: string) {
    return api
      .get<DiscountRule>(`/clinics/${clinicId}/discount-rules`)
      .then((r) => r.data)
  },
}
