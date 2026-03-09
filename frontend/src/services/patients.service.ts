import { api } from './api'
import type { Patient, PatientWithStats, CreatePatientPayload, PaginatedResponse } from '@/types'

export interface ListPatientsParams {
  search?: string
  page?: number
  per_page?: number
}

export const patientsService = {
  list(clinicId: string, params?: ListPatientsParams) {
    return api
      .get<PaginatedResponse<PatientWithStats>>(`/clinics/${clinicId}/patients`, { params })
      .then((r) => r.data)
  },

  get(clinicId: string, patientId: string) {
    return api
      .get<Patient>(`/clinics/${clinicId}/patients/${patientId}`)
      .then((r) => r.data)
  },

  create(clinicId: string, payload: CreatePatientPayload) {
    return api
      .post<Patient>(`/clinics/${clinicId}/patients`, payload)
      .then((r) => r.data)
  },

  update(clinicId: string, patientId: string, payload: Partial<CreatePatientPayload>) {
    return api
      .patch<Patient>(`/clinics/${clinicId}/patients/${patientId}`, payload)
      .then((r) => r.data)
  },
}
