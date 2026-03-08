import { api } from './api'
import type {
  Appointment,
  AppointmentStatus,
  CreateAppointmentPayload,
  UpdateAppointmentPayload,
  PaginatedResponse,
} from '@/types'

export interface ListAppointmentsParams {
  date?: string          // ISO date string YYYY-MM-DD
  week_start?: string    // ISO date string — returns full week
  patient_id?: string
  status?: AppointmentStatus
  page?: number
  per_page?: number
}

export const appointmentsService = {
  list(clinicId: string, params?: ListAppointmentsParams) {
    return api
      .get<PaginatedResponse<Appointment>>(`/clinics/${clinicId}/appointments`, { params })
      .then((r) => r.data)
  },

  get(clinicId: string, appointmentId: string) {
    return api
      .get<Appointment>(`/clinics/${clinicId}/appointments/${appointmentId}`)
      .then((r) => r.data)
  },

  create(clinicId: string, payload: CreateAppointmentPayload) {
    return api
      .post<Appointment>(`/clinics/${clinicId}/appointments`, payload)
      .then((r) => r.data)
  },

  update(clinicId: string, appointmentId: string, payload: UpdateAppointmentPayload) {
    return api
      .patch<Appointment>(`/clinics/${clinicId}/appointments/${appointmentId}`, payload)
      .then((r) => r.data)
  },

  cancel(clinicId: string, appointmentId: string) {
    return api
      .patch<Appointment>(`/clinics/${clinicId}/appointments/${appointmentId}`, {
        status: 'cancelled' satisfies AppointmentStatus,
      })
      .then((r) => r.data)
  },
}
