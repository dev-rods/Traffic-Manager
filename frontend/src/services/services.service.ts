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

export const servicesService = {
  list(clinicId: string) {
    return api
      .get<ListServicesResponse>(`/clinics/${clinicId}/services`)
      .then((r) => r.data.services)
  },
}
