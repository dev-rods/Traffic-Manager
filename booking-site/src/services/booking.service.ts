import { api } from './api'
import type {
  Appointment,
  AvailabilityResponse,
  BootstrapResponse,
  CartPayload,
  CreateAppointmentPayload,
  Quote,
} from '@/types'

export const bookingService = {
  bootstrap: (clinicId: string) =>
    api.get<BootstrapResponse>(`/public/clinics/${clinicId}/bootstrap`).then((r) => r.data),

  // Domínio próprio da clínica (ver CustomDomainField no painel) em vez do
  // clinicId na URL: resolve qual clínica é dona do host atual.
  resolveDomain: (host: string) =>
    api
      .get<{ clinicId: string }>('/public/resolve-domain', { params: { host } })
      .then((r) => r.data.clinicId),

  // Status (CLOSED | FULL | AVAILABLE) + horários livres para uma lista de datas —
  // mesma AvailabilityEngine do bot de WhatsApp. A duração da sessão é calculada
  // pelo backend a partir do carrinho (a mesma que a criação grava), nunca aqui.
  availability: (clinicId: string, dates: string[], cart: CartPayload) =>
    api
      .get<AvailabilityResponse>(`/public/clinics/${clinicId}/availability`, {
        params: {
          dates: dates.join(','),
          serviceIds: cart.serviceIds.join(','),
          serviceAreaPairs:
            cart.serviceAreaPairs.map((p) => `${p.serviceId}:${p.areaId}`).join(',') || undefined,
        },
      })
      .then((r) => ({ days: r.data.days, window: r.data.window })),

  // Total, desconto e valor final — com o telefone, também primeira sessão e
  // desconto personalizado. POST para o telefone não ir na URL.
  quote: (clinicId: string, cart: CartPayload, phone?: string) =>
    api
      .post<{ quote: Quote }>(`/public/clinics/${clinicId}/quote`, { ...cart, phone })
      .then((r) => r.data.quote),

  sendOtp: (clinicId: string, phone: string) =>
    api
      .post<{ status: string }>(`/public/clinics/${clinicId}/verify/send`, { phone })
      .then((r) => r.data),

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
      .post<{
        appointment: Appointment
      }>(`/public/clinics/${clinicId}/appointments/${appointmentId}/cancel`, { phone, token })
      .then((r) => r.data.appointment),
}
