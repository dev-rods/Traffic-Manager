import { api } from './api'
import type {
  ListAppointmentsResponse,
  CreateAppointmentPayload,
  UpdateAppointmentPayload,
} from '@/types'

export interface ListAppointmentsParams {
  date?: string
  date_from?: string
  date_to?: string
  status?: string
}

export const appointmentsService = {
  list(clinicId: string, params?: ListAppointmentsParams) {
    return api
      .get<ListAppointmentsResponse>(`/clinics/${clinicId}/appointments`, { params })
      .then((r) => r.data)
  },

  create(payload: CreateAppointmentPayload) {
    return api
      .post('/appointments', payload)
      .then((r) => r.data)
  },

  update(appointmentId: string, payload: UpdateAppointmentPayload) {
    return api
      .put(`/appointments/${appointmentId}`, payload)
      .then((r) => r.data)
  },

  cancel(appointmentId: string) {
    return api
      .put(`/appointments/${appointmentId}`, { status: 'CANCELLED' })
      .then((r) => r.data)
  },

  /** A pessoa nao compareceu. O backend recusa se a sessao ainda nao passou. */
  marcarFalta(appointmentId: string) {
    return api
      .put(`/appointments/${appointmentId}`, { status: 'NO_SHOW' })
      .then((r) => r.data)
  },

  /** Desfaz a falta. `CONFIRMED` sobre NO_SHOW e o desmarcar; sobre CANCELLED
   *  o backend devolve 409, porque o horario pode ter sido reocupado. */
  desmarcarFalta(appointmentId: string) {
    return api
      .put(`/appointments/${appointmentId}`, { status: 'CONFIRMED' })
      .then((r) => r.data)
  },
}
