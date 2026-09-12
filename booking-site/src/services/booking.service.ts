import { api } from './api'
import type { Appointment, BootstrapResponse, CreateAppointmentPayload } from '@/types'

export const bookingService = {
  bootstrap: (clinicId: string) =>
    api.get<BootstrapResponse>(`/public/clinics/${clinicId}/bootstrap`).then((r) => r.data),

  availableSlots: (
    clinicId: string,
    params: { date: string; serviceId: string; totalDuration?: number }
  ) =>
    api
      .get<{ slots: string[] }>(`/public/clinics/${clinicId}/available-slots`, {
        params: {
          date: params.date,
          serviceId: params.serviceId,
          totalDuration: params.totalDuration,
        },
      })
      .then((r) => r.data.slots),

  sendOtp: (clinicId: string, phone: string) =>
    api.post<{ status: string }>(`/public/clinics/${clinicId}/verify/send`, { phone }).then((r) => r.data),

  confirmOtp: (clinicId: string, phone: string, code: string) =>
    api
      .post<{ token: string }>(`/public/clinics/${clinicId}/verify/confirm`, { phone, code })
      .then((r) => r.data.token),

  createAppointment: (clinicId: string, payload: CreateAppointmentPayload) =>
    api
      .post<{ appointment: Appointment }>(`/public/clinics/${clinicId}/appointments`, payload)
      .then((r) => r.data.appointment),

  myAppointments: (clinicId: string, phone: string, token: string) =>
    api
      .get<{ appointments: Appointment[] }>(`/public/clinics/${clinicId}/my-appointments`, {
        params: { phone, token },
      })
      .then((r) => r.data.appointments),

  cancelAppointment: (clinicId: string, appointmentId: string, phone: string, token: string) =>
    api
      .post<{ appointment: Appointment }>(
        `/public/clinics/${clinicId}/appointments/${appointmentId}/cancel`,
        { phone, token }
      )
      .then((r) => r.data.appointment),
}
