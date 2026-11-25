import { api } from './api'
import type {
  Appointment,
  AvailabilityResponse,
  BootstrapResponse,
  CadastroPayload,
  CartPayload,
  ConfirmOtpResult,
  CreateAppointmentPayload,
  PacienteVerificado,
  Quote,
  RescheduleAppointmentPayload,
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
  // `excludeAppointmentId`: a grade para REMARCAR esse agendamento, sem que
  // ele ocupe o próprio horário (PRD 035).
  availability: (clinicId: string, cart: CartPayload, excludeAppointmentId?: string) =>
    api
      .get<AvailabilityResponse>(`/public/clinics/${clinicId}/availability`, {
        params: {
          serviceIds: cart.serviceIds.join(','),
          serviceAreaPairs:
            cart.serviceAreaPairs.map((p) => `${p.serviceId}:${p.areaId}`).join(',') || undefined,
          excludeAppointmentId,
        },
      })
      .then((r) => ({ days: r.data.days })),

  // Total, desconto e valor final. Com celular E token de sessão, também
  // primeira sessão e desconto personalizado: o preço da pessoa só sai depois
  // do código (PRD 061), senão qualquer um veria o desconto de outra pelo
  // número. POST para o telefone não ir na URL.
  quote: (clinicId: string, cart: CartPayload, phone?: string, token?: string) =>
    api
      .post<{ quote: Quote }>(`/public/clinics/${clinicId}/quote`, { ...cart, phone, token })
      .then((r) => r.data.quote),

  sendOtp: (clinicId: string, phone: string) =>
    api
      .post<{ status: string }>(`/public/clinics/${clinicId}/verify/send`, { phone })
      .then((r) => r.data),

  // Além do token, no escopo de sessão vem `paciente` ({nome, faltam} ou
  // null): só depois do código o site fica sabendo de quem é o número (PRD 061).
  confirmOtp: (clinicId: string, phone: string, code: string) =>
    api
      .post<ConfirmOtpResult>(`/public/clinics/${clinicId}/verify/confirm`, { phone, code })
      .then((r) => ({ token: r.data.token, paciente: r.data.paciente ?? null })),

  // Cria ou completa a ficha SEM agendamento (PRD 061). Só com phone e token
  // devolve o estado da ficha sem gravar nada.
  cadastro: (clinicId: string, payload: CadastroPayload) =>
    api
      .post<{ paciente: PacienteVerificado }>(`/public/clinics/${clinicId}/cadastro`, payload)
      .then((r) => r.data.paciente ?? null),

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

  rescheduleAppointment: (
    clinicId: string,
    appointmentId: string,
    body: RescheduleAppointmentPayload
  ) =>
    api
      .post<{
        appointment: Appointment
      }>(`/public/clinics/${clinicId}/appointments/${appointmentId}/reschedule`, body)
      .then((r) => r.data.appointment),

  cancelAppointment: (clinicId: string, appointmentId: string, phone: string, token: string) =>
    api
      .post<{
        appointment: Appointment
      }>(`/public/clinics/${clinicId}/appointments/${appointmentId}/cancel`, { phone, token })
      .then((r) => r.data.appointment),
}
