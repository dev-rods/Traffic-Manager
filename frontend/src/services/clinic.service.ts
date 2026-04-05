import { api } from './api'
import type { Clinic, UpdateClinicPayload } from '@/types'

interface GetClinicResponse {
  status: string
  clinic: Clinic
}

export const clinicService = {
  get(clinicId: string) {
    return api
      .get<GetClinicResponse>(`/clinics/${clinicId}`)
      .then((r) => r.data.clinic)
  },

  update(clinicId: string, payload: UpdateClinicPayload) {
    return api
      .put<GetClinicResponse>(`/clinics/${clinicId}`, payload)
      .then((r) => r.data.clinic)
  },
}
