import { api } from './api'

export interface ClinicService {
  id: string
  clinic_id: string
  name: string
  duration_minutes: number
  price_cents: number | null
  description: string | null
  active: boolean
}

interface ListServicesResponse {
  status: string
  services: ClinicService[]
}

interface ServiceResponse {
  status: string
  service: ClinicService
}

export interface CreateServicePayload {
  name: string
  duration_minutes: number
  price_cents?: number
  description?: string
}

export interface UpdateServicePayload {
  name?: string
  duration_minutes?: number
  price_cents?: number
  description?: string
  active?: boolean
}

export const servicesService = {
  list(clinicId: string) {
    return api
      .get<ListServicesResponse>(`/clinics/${clinicId}/services`)
      .then((r) => r.data.services)
  },

  create(clinicId: string, payload: CreateServicePayload) {
    return api
      .post<ServiceResponse>(`/clinics/${clinicId}/services`, payload)
      .then((r) => r.data.service)
  },

  update(serviceId: string, payload: UpdateServicePayload) {
    return api
      .put<ServiceResponse>(`/services/${serviceId}`, payload)
      .then((r) => r.data.service)
  },
}
