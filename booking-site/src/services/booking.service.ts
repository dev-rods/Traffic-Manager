import { api } from './api'
import type { Appointment, BootstrapResponse, CreateAppointmentPayload, DayAvailability } from '@/types'

export const bookingService = {
  bootstrap: (clinicId: string) =>
    api.get<BootstrapResponse>(`/public/clinics/${clinicId}/bootstrap`).then((r) => r.data),

  // Status (CLOSED | FULL | AVAILABLE) + horários livres para uma lista de datas —
  // mesma AvailabilityEngine do bot de WhatsApp (get_days_status). Uma chamada só
  // já traz tudo que o seletor de semana precisa (dias abertos/lotados) e os
  // horários da data selecionada, sem endpoint separado de slots.
  weekAvailability: (clinicId: string, dates: string[], totalDuration: number) =>
    api
      .get<{ days: Record<string, DayAvailability> }>(`/public/clinics/${clinicId}/availability`, {
        params: { dates: dates.join(','), totalDuration },
      })
      .then((r) => r.data.days),

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
